"""Docker related functions"""

from __future__ import annotations

import os

import docker.errors  # type: ignore
import docker.types  # type: ignore
from docker import DockerClient
from docker.models.containers import Container  # type: ignore
from par_ai_core.utils import read_env_file


# pylint: disable=too-many-arguments,too-many-return-statements,too-many-branches
def start_docker_container(
    image: str,
    *,
    container_name: str,
    command: str | None = None,
    env: dict | None = None,
    ports: dict | None = None,
    network_name: str | None = None,
    mounts: list[docker.types.Mount] | None = None,
    re_create: bool = False,
    remove: bool = False,
    background: bool = True,
) -> str | Container | Exception:
    """
    Start a docker container if it exists, otherwise create it

    Args:
        image (str): The base image to use
        container_name (str): The name of the container
        command (str | None): The command line to run. Defaults to None
        env (dict | None): The environment variables to use. Defaults to None
        ports (dict | None): The ports to expose. Defaults to None
        network_name (str | None): The network to use. Defaults to None
        mounts (List[docker.types.Mount]): The mounts to use.
            Example: [docker.types.Mount(target="/workspace", source=f"{os.getcwd()}/output/{parent_id}", type="bind")]
        re_create (bool): Whether to recreate the container if it exists. Defaults to False
        remove (bool): Whether to remove the container after execution. Defaults to False
        background (bool): Whether to run the container in the background. Defaults to True

    Returns:
        bool: True if successful, False otherwise
    """

    try:
        if not env:
            env = {}
        env = read_env_file(".env") | env
        client: DockerClient
        if os.name == "nt":
            client = docker.DockerClient(base_url="tcp://127.0.0.1:2375", tls=False)
        else:
            client = docker.DockerClient(base_url="unix://var/run/docker.sock")
        if network_name:
            try:
                networks = client.networks.list(names=[network_name])
                if len(networks) > 0:
                    # network = networks[0]
                    print(f"Network {network_name} exists.")
                else:
                    client.networks.create(network_name, driver="bridge")
                    print(f"Network {network_name} created")
            except docker.errors.APIError as e:
                return e

        container: Container
        # container = client.containers.list(all=True, filters={"name": container_name})
        try:
            container = client.containers.get(container_name)
            # print(f"Container {container_name} exists.")
            if re_create:
                # print(f"Recreating container {container_name}")
                container.remove(force=True)
            else:
                if container.status == "running":
                    # print(f"Container {container_name} is already running.")
                    return container
                # print(f"Starting container {container_name}")
                container.start()
                return container
        except docker.errors.NotFound:
            pass
        except docker.errors.APIError as e:
            return e

        print(f"Container {container_name} does not exist. Creating...")
        if background:
            container = client.containers.run(
                image,
                command,
                name=container_name,
                ports=ports,
                detach=background,
                environment=env,
                remove=remove,
                network=network_name,
                mounts=mounts,
            )
            return container
        logs: bytes = client.containers.run(
            image,
            command,
            name=container_name,
            ports=ports,
            detach=background,
            environment=env,
            remove=remove,
            network=network_name,
            mounts=mounts,
        )
        return logs.decode("utf-8").strip()
    except docker.errors.DockerException as e:
        return e
