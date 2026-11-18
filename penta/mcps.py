from composer.config import Server
from composer.enum import ServerTransport

taskmanager_server = Server(
    name="taskmanager",
    transport=ServerTransport.HTTP,
    url="http://localhost:8008/mcp",
)

webagent_server = Server(
    name="webagent",
    transport=ServerTransport.HTTP,
    url="http://localhost:3333/mcp",
)

recon_server = Server(
    name="recon",
    transport=ServerTransport.STDIO,
    command="docker",
    args=["run", "--network=host", "-i", "--rm", "cyberillo/kali-mcp-server:latest"],
)