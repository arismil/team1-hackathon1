from langchain_core.tools import tool

@tool
def search_logs(service:str) -> str:
    """Search logs for a specific service to identify errors."""
    try:
        if service not in SERVICES:
            return f"Error: No logs found for service '{service}'."

        logs = "\n".join(LOGS[service]) # Na parw ola ta logs h merika???????????
        return f"Logs for {service}: \n{logs}"
    except Exception as e:
        return f"Tool excecution failed: {str(e)}"

@tool
def get_service_metrics(service:str) -> str:
    """Fetches current operational metrics for a given service."""
    try:
        if service not in SERVICES:
            return f"Error: No logs found for service '{service}'."

        metrics = METRICS[]        
        return
    except Exception as e:
        return f"Tool excecution failed: {str(e)}"

@tool
def search_knowledge_base(query):
    try:
        
        return
    except Exception as e:
        return f"Tool excecution failed: {str(e)}"

@tool    
def get_incident_history(service:str) -> str:
    """ """
    try:
        if service not in SERVICES:
            return f"Error: No logs found for service '{service}'."


        return
    except Exception as e:
        return f"Tool excecution failed: {str(e)}"

@tool    
def restart_service(service:str) -> str:
    """ """
    try:
        if service not in SERVICES:
            return f"Error: No logs found for service '{service}'."


        return
    except Exception as e:
        return f"Tool excecution failed: {str(e)}"

@tool    
def check_service_health(service:str) -> str:
    """ """
    try:
        if service not in SERVICES:
            return f"Error: No logs found for service '{service}'."


        return
    except Exception as e:
        return f"Tool excecution failed: {str(e)}"