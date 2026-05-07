from metagpt.actions.action import Action


class WriteExecutionReport(Action):
    """Marker action published by BIAnalyticsEngineer when the DWH execution report is complete.

    BIQAEngineer watches for this action type to trigger structural and requirements
    traceability validation.  The execution report itself is written directly by
    BIAnalyticsEngineer using Editor; this class serves only as the cause_by type on
    the published message so that downstream agents can observe it.
    """

    name: str = "WriteExecutionReport"
