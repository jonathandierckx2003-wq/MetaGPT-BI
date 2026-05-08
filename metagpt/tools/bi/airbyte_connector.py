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

    def configure(
        self,
        client_id: str,
        client_secret: str,
        workspace_id: str,
        base_url: str | None = None,
    ) -> str:
        """Initialise the Airbyte API client using OAuth2 client credentials.

        Performs the client-credentials token exchange manually (POST to
        /applications/token) so we are not dependent on the SDK's built-in
        OAuth2 handling, which proved unreliable in practice (DEV-55).

        Args:
            client_id: Application client ID (Airbyte Cloud > User Settings >
                       Applications > your application).
            client_secret: Application client secret.
            workspace_id: Airbyte workspace ID (visible in the Airbyte Cloud URL).
            base_url: Override the Airbyte API base URL.
                      Defaults to 'https://api.airbyte.com/v1'.

        Returns:
            Confirmation string.
        """
        import requests as _requests
        from airbyte_api import AirbyteAPI
        from airbyte_api.models import Security

        api_base = (base_url or "https://api.airbyte.com/v1").rstrip("/")
        token_url = f"{api_base}/applications/token"

        resp = _requests.post(
            token_url,
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Airbyte token exchange failed (HTTP {resp.status_code}): {resp.text}. "
                "Verify the client_id and client_secret in Airbyte Cloud > "
                "User Settings > Applications."
            )

        access_token = resp.json().get("access_token") or resp.json().get("accessToken")
        if not access_token:
            raise RuntimeError(
                f"Airbyte token response missing 'access_token' field: {resp.text}"
            )

        self._client = AirbyteAPI(
            security=Security(bearer_auth=access_token),
            server_url=api_base,
        )
        self._workspace_id = workspace_id
        return f"Airbyte client configured (workspace: {workspace_id})."

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError(
                "Airbyte client not configured. Call configure(client_id, client_secret, workspace_id) first."
            )
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

    # Maps lowercase source_type strings to the SDK's typed SourceXxx dataclass.
    # The Airbyte Cloud Public API v1 dropped support for definitionId on standard
    # sources (STANDARD_SOURCE_DEFINITION 404); callers must use sourceType instead.
    _SOURCE_TYPE_MAP: dict[str, str] = {
        "faker": "SourceFaker",
    }

    def setup_connection(self, source_config: dict[str, Any]) -> dict[str, Any]:
        """Create an Airbyte source and connection pointing at an existing destination.

        The `source_config` dict must contain:
          - 'source_type' (str): Lowercase connector type (e.g. 'faker').
            Preferred for standard Airbyte Cloud connectors — maps to the SDK's
            typed SourceXxx dataclass so no definitionId is needed.
          - 'source_name' (str): Display name for the source.
          - 'source_connection_config': Dict of connector-specific params.
          - 'destination_id' (str): ID of an already-existing Airbyte destination.
          - 'stream_names' (list[str], optional): Subset of stream names to sync.

        Returns:
            Dict with 'source_id', 'connection_id', and 'streams' (list synced).

        Example source_config for Faker::

            {
                "source_type": "faker",
                "source_name": "Sample Data Faker",
                "source_connection_config": {"count": 1000, "seed": 42},
                "destination_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                "stream_names": ["users", "products", "purchases"],
            }
        """
        import airbyte_api.models as models

        client = self._require_client()

        # Build typed configuration when source_type is known; fall back to
        # definition_id for private/custom connectors that still use that path.
        src_type = source_config.get("source_type", "").lower()
        cfg_params = source_config.get("source_connection_config") or {}
        if src_type in self._SOURCE_TYPE_MAP:
            cls_name = self._SOURCE_TYPE_MAP[src_type]
            cfg_cls = getattr(models, cls_name)
            # Build only with params the dataclass actually accepts
            import dataclasses
            valid_fields = {f.name for f in dataclasses.fields(cfg_cls)}
            filtered = {k: v for k, v in cfg_params.items() if k in valid_fields}
            configuration = cfg_cls(**filtered)
            definition_id = None
        else:
            configuration = cfg_params
            definition_id = source_config.get("source_definition_id")

        source_resp = client.sources.create_source(
            request=models.SourceCreateRequest(
                workspace_id=self._workspace_id,
                name=source_config["source_name"],
                configuration=configuration,
                definition_id=definition_id,
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

        If a sync is already running for the connection (HTTP 409), the running
        job is fetched and returned so wait_for_sync() can poll it without
        triggering a duplicate (DEV-56).

        Args:
            connection_id: Airbyte connection ID returned by setup_connection().

        Returns:
            Dict with 'job_id' and 'status'.
        """
        import airbyte_api.api.listjobs as lj
        import airbyte_api.models as models

        client = self._require_client()
        try:
            resp = client.jobs.create_job(
                request=models.JobCreateRequest(
                    connection_id=connection_id,
                    job_type=models.JobTypeEnum.SYNC,
                )
            )
            job = resp.job_response
            return {"job_id": job.job_id, "status": job.status}
        except Exception as exc:
            if "409" in str(exc) or "already running" in str(exc).lower():
                # A sync is already in progress — find it and return its job_id
                list_resp = client.jobs.list_jobs(
                    request=lj.ListJobsRequest(connection_id=connection_id, limit=1)
                )
                jobs = list_resp.jobs_response.data if list_resp.jobs_response else []
                if jobs:
                    running = jobs[0]
                    return {"job_id": running.job_id, "status": running.status}
            raise

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

        import airbyte_api.api.getjob as gj

        client = self._require_client()
        resp = client.jobs.get_job(request=gj.GetJobRequest(job_id=int(job_id)))
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
