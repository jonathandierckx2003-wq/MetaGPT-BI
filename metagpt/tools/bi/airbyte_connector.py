from __future__ import annotations

import time
from typing import Any

from metagpt.tools.tool_registry import register_tool

TAGS = ["bi", "airbyte", "ingestion"]


@register_tool(tags=TAGS)
class AirbyteConnector:
    """Interact with an Airbyte instance via the Airbyte API SDK.

    Supports both Airbyte Cloud (cloud.airbyte.com) and self-hosted Airbyte
    instances via a configurable base URL.

    Typical workflow for a DATA_INGESTION task:
      1. Call setup_connection() to create a source + destination + connection.
      2. Call trigger_sync(connection_id) to start the data sync job.
      3. Poll get_sync_status(job_id) until the status is 'succeeded' or 'failed'.

    The Airbyte API client is lazily created when configure() is called.
    """

    POLL_INTERVAL = 10
    MAX_POLL_ATTEMPTS = 60

    def __init__(self):
        self._client = None
        self._workspace_id: str | None = None

    def configure(self, api_key: str, workspace_id: str, base_url: str | None = None) -> str:
        """Initialise the Airbyte API client.

        Args:
            api_key: Airbyte API key (from Airbyte Cloud or self-hosted admin UI).
            workspace_id: Airbyte workspace ID (visible in the Airbyte UI URL).
            base_url: Base URL of the Airbyte API. Defaults to Airbyte Cloud.
                      For self-hosted: 'http://localhost:8000' (or your server URL).

        Returns:
            Confirmation string.
        """
        import airbyte_api
        from airbyte_api import AirbyteAPI

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["server_url"] = base_url

        self._client = AirbyteAPI(**kwargs)
        self._workspace_id = workspace_id
        return f"Airbyte client configured (workspace: {workspace_id})."

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("Airbyte client not configured. Call configure() first.")
        return self._client

    def create_destination(self, destination_config: dict[str, Any]) -> dict[str, Any]:
        """Create an Airbyte destination (e.g. PostgreSQL / Supabase) and return its ID.

        The `destination_config` dict must contain:
          - 'destination_name' (str): Display name for the destination.
          - 'destination_definition_id' (str): Airbyte destination type UUID.
            PostgreSQL / Supabase: '25c5221d-dce2-4163-ade9-739ef790f503'
          - 'destination_connection_config': Connector-specific configuration dict.
            For PostgreSQL / Supabase::

                {
                    "host": "db.<ref>.supabase.co",
                    "port": 5432,
                    "database": "postgres",
                    "username": "postgres",
                    "password": "<your_db_password>",
                    "schema": "public",
                    "ssl_mode": {"mode": "require"},
                }

        If the API call fails (e.g. wrong definition ID), raises RuntimeError with
        manual-setup instructions so the human user can create the destination in the
        Airbyte Cloud UI and supply the destination_id.

        Returns:
            Dict with 'destination_id' and 'name'.

        Example destination_config::

            {
                "destination_name": "Supabase DWH",
                "destination_definition_id": "25c5221d-dce2-4163-ade9-739ef790f503",
                "destination_connection_config": {
                    "host": "db.xxx.supabase.co",
                    "port": 5432,
                    "database": "postgres",
                    "username": "postgres",
                    "password": "...",
                    "schema": "public",
                    "ssl_mode": {"mode": "require"},
                },
            }
        """
        import airbyte_api.models as models

        client = self._require_client()
        try:
            resp = client.destinations.create_destination(
                request=models.DestinationCreateRequest(
                    workspace_id=self._workspace_id,
                    name=destination_config["destination_name"],
                    definition_id=destination_config["destination_definition_id"],
                    configuration=destination_config["destination_connection_config"],
                )
            )
            destination_id = resp.destination_response.destination_id
            return {
                "destination_id": destination_id,
                "name": destination_config["destination_name"],
                "status": "created",
            }
        except Exception as exc:
            raise RuntimeError(
                f"Failed to create Airbyte destination via API: {exc}. "
                "MANUAL FALLBACK: Please create a PostgreSQL destination in the Airbyte Cloud UI: "
                "1. Go to cloud.airbyte.com → Destinations → New destination. "
                "2. Search for 'PostgreSQL' and select it. "
                "3. Fill in your Supabase host, port (5432), database (postgres), "
                "username (postgres), password, schema (public), SSL mode (require). "
                "4. Save and copy the destination ID from the destination detail page URL. "
                "Then supply that destination_id to the agent."
            ) from exc

    def setup_connection(self, source_config: dict[str, Any]) -> dict[str, Any]:
        """Create an Airbyte source and connection pointing at an existing destination.

        The `source_config` dict must contain:
          - 'source_definition_id' (str): Airbyte source definition ID.
          - 'source_name' (str): Display name for the source.
          - 'source_connection_config': Connector-specific configuration object
            (use the appropriate airbyte_api.models.Source* dataclass or a plain dict).
          - 'destination_id' (str): ID of an already-existing Airbyte destination.
          - 'stream_names' (list[str], optional): Subset of stream names to sync.
            Omit to sync all available streams.

        Returns:
            Dict with 'source_id', 'connection_id', and 'streams' (list synced).

        Example source_config::

            {
                "source_definition_id": "778daa7c-feaf-4db6-96f3-70fd645acc77",
                "source_name": "Sales CSV",
                "source_connection_config": <SourceCsv instance or config dict>,
                "destination_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "stream_names": ["sales"],
            }
        """
        import airbyte_api.models as models

        client = self._require_client()

        source_resp = client.sources.create_source(
            request=models.SourceCreateRequest(
                workspace_id=self._workspace_id,
                name=source_config["source_name"],
                definition_id=source_config["source_definition_id"],
                configuration=source_config["source_connection_config"],
            )
        )
        source_id = source_resp.source_response.source_id

        streams = source_config.get("stream_names")
        stream_configs = None
        if streams:
            stream_configs = [
                models.StreamConfiguration(
                    name=s,
                    sync_mode=models.ConnectionSyncModeEnum.FULL_REFRESH_OVERWRITE,
                )
                for s in streams
            ]

        conn_resp = client.connections.create_connection(
            request=models.ConnectionCreateRequest(
                source_id=source_id,
                destination_id=source_config["destination_id"],
                name=f"conn_{source_config['source_name']}",
                configurations=models.StreamConfigurationsInput(streams=stream_configs)
                if stream_configs
                else None,
            )
        )
        connection_id = conn_resp.connection_response.connection_id

        return {
            "source_id": source_id,
            "connection_id": connection_id,
            "streams": streams or ["all"],
        }

    def trigger_sync(self, connection_id: str) -> dict[str, Any]:
        """Trigger an Airbyte sync job for an existing connection.

        Args:
            connection_id: Airbyte connection ID returned by setup_connection().

        Returns:
            Dict with 'job_id' and 'status' (initial status, usually 'pending').
        """
        import airbyte_api.models as models

        client = self._require_client()
        resp = client.jobs.create_job(
            request=models.JobCreateRequest(
                connection_id=connection_id,
                job_type=models.JobTypeEnum.SYNC,
            )
        )
        job = resp.job_response
        return {"job_id": job.job_id, "status": job.status}

    def get_sync_status(self, job_id: str) -> dict[str, Any]:
        """Check the current status of an Airbyte sync job.

        Args:
            job_id: Job ID returned by trigger_sync().

        Returns:
            Dict with 'job_id', 'status' (one of: 'pending', 'running',
            'succeeded', 'failed', 'cancelled'), and optional 'error_message'.

        Note:
            The LLM can poll this method in the ReAct loop until 'succeeded'
            or 'failed' is returned.  For a blocking wait, use wait_for_sync().
        """
        import airbyte_api.models as models

        client = self._require_client()
        resp = client.jobs.get_job(job_id=int(job_id))
        job = resp.job_response
        status_value = job.status.value if hasattr(job.status, "value") else str(job.status)
        return {"job_id": job_id, "status": status_value}

    def wait_for_sync(self, job_id: str) -> dict[str, Any]:
        """Block until an Airbyte sync job reaches a terminal state.

        Polls get_sync_status() at POLL_INTERVAL-second intervals up to
        MAX_POLL_ATTEMPTS times.  Use this in the ReAct loop when the LLM
        does not need to perform any other actions while waiting.

        Args:
            job_id: Job ID returned by trigger_sync().

        Returns:
            Final status dict from get_sync_status().

        Raises:
            TimeoutError: If the job does not complete within the polling window.
            RuntimeError: If the job fails.
        """
        for _ in range(self.MAX_POLL_ATTEMPTS):
            status_dict = self.get_sync_status(job_id)
            status = status_dict["status"]
            if status == "succeeded":
                return status_dict
            if status in ("failed", "cancelled", "incomplete"):
                raise RuntimeError(
                    f"Airbyte job {job_id} ended with status '{status}': "
                    f"{status_dict.get('error_message', 'no details')}"
                )
            time.sleep(self.POLL_INTERVAL)

        raise TimeoutError(
            f"Airbyte job {job_id} did not complete after "
            f"{self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL} seconds."
        )

    def list_connections(self) -> list[dict[str, Any]]:
        """List all connections in the configured workspace.

        Returns:
            List of dicts with 'connection_id', 'name', 'status', 'source_id', 'destination_id'.
        """
        client = self._require_client()
        resp = client.connections.list_connections(workspace_id=self._workspace_id)
        connections = []
        for c in resp.connections_response.data:
            connections.append(
                {
                    "connection_id": c.connection_id,
                    "name": c.name,
                    "status": c.status,
                    "source_id": c.source_id,
                    "destination_id": c.destination_id,
                }
            )
        return connections
