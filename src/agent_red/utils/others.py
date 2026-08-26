import asyncio
from typing import Callable, Awaitable, Any, Optional, List
import os
import pdb
import time
import socket
import docker, io, tarfile, os
import re
from .log import logger

def _sanitize_for_json(obj):
    """Recursively strip null bytes and other illegal characters from all strings"""
    if isinstance(obj, str):
        # Remove null bytes and other control characters (keep newlines, tabs, etc.)
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', obj)
    elif isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    else:
        return obj


def get_container_file_content(container, file_path: str) -> str:
    """
    Retrieves the content of a specified file from within a Docker container.
    
    Args:
        container: The Docker container object.
        file_path: The path to the file inside the container.
    Returns:
        The content of the file as a string.
    """
    bits, stat = container.get_archive(file_path)
    tar_bytes = b"".join(bits)

    # 2. Open tar archive in memory
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        member = tar.getmembers()[0]      # usually only one file
        file_obj = tar.extractfile(member)
        content_bytes = file_obj.read()

    # 3. Decode to string
    return content_bytes.decode("utf-8")

def docker_write_str_to_file(data, filename, container_name="my-code-server-redteam", container=None, target_user=None):
    client = docker.from_env()
    if container is None:
        container = client.containers.get(container_name)
    # container.exec_run(['bash', '-c', f'echo "{data}" > {filename}'])

    # Ensure parent directory exists in the container
    parent_dir = os.path.dirname(filename) or '/'
    if parent_dir != '/':
        container.exec_run(['mkdir', '-p', parent_dir])

    container.exec_run(['rm', '-f', filename])
    # Create a tarfile in memory
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as tar:
        encoded_data = data.encode('utf-8')
        tarinfo = tarfile.TarInfo(name=os.path.basename(filename))
        tarinfo.size = len(encoded_data)
        tar.addfile(tarinfo, io.BytesIO(encoded_data))

    # Reset stream position
    stream.seek(0)

    # Upload the tarball to the container (extracts automatically)
    # Note: 'path' must be the parent directory of where you want the file
    container.put_archive(path=parent_dir, data=stream)
    
    # Change file ownership if target_user is specified
    if target_user:
        container.exec_run(['chown', f'{target_user}:{target_user}', filename])

def docker_cp_to_container(src_path, dst_path, container_name="my-code-server-redteam", container=None, target_user=None):
    client = docker.from_env()
    if container is None:
        container = client.containers.get(container_name)

    src_path = os.path.abspath(src_path)
    base_name = os.path.basename(src_path.rstrip("/"))

    # 2. Create tar archive
    tarstream = io.BytesIO()
    with tarfile.open(fileobj=tarstream, mode='w') as tar:
        tar.add(src_path, arcname=base_name)

    tarstream.seek(0)

    # 3. Upload
    container.put_archive(dst_path, tarstream.read())
    if target_user:
        container.exec_run(['chown', '-R', f'{target_user}:{target_user}', os.path.join(dst_path, base_name)])

def docker_setup_helper_container(setup_script: str, container_name="my-code-server-redteam", container=None):
    client = docker.from_env()
    if container is None:
        container = client.containers.get(container_name)

    # 1. Write setup script to the container
    docker_write_str_to_file(setup_script, "/root/setup.sh", container=container)

    # 2. Make the script executable
    container.exec_run(['chmod', '+x', '/tmp/setup.sh'])

    # 3. Run the setup script
    container.exec_run(['/tmp/setup.sh'])
    
    # 4. Clean up the script
    container.exec_run(['rm', '/tmp/setup.sh'])


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return False
        except:
            return True

def find_available_port(start_port: int = 8000, max_attempts: int = 100, except_ports: list[int] = []) -> int:
    attempts = 0
    while attempts < max_attempts:
        port = start_port + attempts
        if port not in except_ports and not is_port_in_use(port):
            return port
        attempts += 1


def retry_sync(
    func: Callable[..., Any],
    *args,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs
) -> Any:
    """
    Retry a sync function with exponential backoff.
    
    Args:
        func: The sync function to retry
        *args: Positional arguments to pass to the function
        max_attempts: Maximum number of attempts (default: 3)
        delay: Initial delay between retries in seconds (default: 1.0)
        backoff: Multiplier applied to delay after each retry (default: 2.0)
        exceptions: Tuple of exceptions to catch and retry on (default: (Exception,))
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the successful function call
        
    Raises:
        The last exception that occurred if all attempts failed
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:  # Don't log on the last attempt
                logger.warning(
                    f"Attempt {attempt + 1} failed with exception: {e}. "
                    f"Retrying in {delay} seconds..."
                )
                time.sleep(delay)
                delay *= backoff
            else:
                logger.error(f"All {max_attempts} attempts failed. Last exception: {e}")
    
    # If we got here, all attempts failed
    raise last_exception or Exception("Function failed after retries.")

async def retry(
    func: Callable[..., Awaitable[Any]],
    *args,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: The async function to retry
        *args: Positional arguments to pass to the function
        max_attempts: Maximum number of attempts (default: 3)
        delay: Initial delay between retries in seconds (default: 1.0)
        backoff: Multiplier applied to delay after each retry (default: 2.0)
        exceptions: Tuple of exceptions to catch and retry on (default: (Exception,))
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        The result of the successful function call
        
    Raises:
        The last exception that occurred if all attempts failed
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:  # Don't log on the last attempt
                logger.warning(
                    f"Attempt {attempt + 1} failed with exception: {e}. "
                    f"Retrying in {delay} seconds..."
                )
                await asyncio.sleep(delay)
                delay *= backoff
            else:
                logger.error(f"All {max_attempts} attempts failed. Last exception: {e}")
    
    # If we got here, all attempts failed
    raise last_exception

def safe_decode_content(output: bytes) -> str:
    """Safely decode content, handling binary files appropriately."""
    # Check if content contains null bytes (common in binary files)
    if b'\x00' in output:
        logger.warning("File appears to contain binary data")
        # For binary files, we can still try to decode with errors='replace'
        return output.decode('utf-8', errors='replace')
    
    # Try UTF-8 first
    try:
        return output.decode('utf-8')
    except UnicodeDecodeError:
        # Fall back to latin-1 which can decode any byte
        logger.warning(f"File contains non-UTF-8 characters, falling back to latin-1 decoding")
        return output.decode('latin-1')