"""Opt-in real Node creator integration; no models, credentials, or existing servers."""

import asyncio
import os
import shutil
import socket
import subprocess
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from deck_router.app import create_app as create_router_app
from deck_router.identifiers import decode_id
from deck_router.utils.settings import Settings
from downstream_mock.api import create_app as create_mock_app
from pydantic import HttpUrl
from test_downstream_mock import FixedSelector

pytestmark = pytest.mark.skipif(
    os.environ.get("DECK_ROUTER_BUILDER_INTEGRATION_TESTS") != "1",
    reason="Opt in to the built Node creator with DECK_ROUTER_BUILDER_INTEGRATION_TESTS=1",
)


@pytest.fixture
def builder_url() -> Iterator[str]:
    """Start an isolated compiled creator and always stop only its own process."""
    node = shutil.which("node")
    assert node is not None, "Activate Node on PATH before opting in to builder integration"
    root = Path(__file__).resolve().parents[3]
    script = root / "src" / "deck-builder" / "dist" / "server.js"
    assert script.is_file(), "Build the creator with: npm --prefix src\\deck-builder run build"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as output:
        process = subprocess.Popen(
            [node, str(script)],
            cwd=root,
            env={**os.environ, "DECK_BUILDER_PORT": str(port)},
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 15
            with httpx.Client(timeout=0.5, trust_env=False) as client:
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        output.seek(0)
                        pytest.fail(f"Node creator exited during startup: {output.read()}")
                    try:
                        response = client.get(f"{url}/ping")
                    except httpx.TransportError:
                        time.sleep(0.05)
                        continue
                    if response.status_code == 200 and response.text == "pong":
                        break
                    time.sleep(0.05)
                else:
                    output.seek(0)
                    pytest.fail(f"Node creator was not ready within 15 seconds: {output.read()}")
            yield url
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def test_given_node_creator_when_router_forwards_then_relays_exact_placeholder(
    builder_url: str,
) -> None:
    async def run() -> None:
        mock_app = create_mock_app()
        async with mock_app.router.lifespan_context(mock_app):
            async with httpx.AsyncClient(
                mounts={"http://editor.test": httpx.ASGITransport(app=mock_app)},
                timeout=5,
                trust_env=False,
            ) as downstream:
                router_app = create_router_app(
                    Settings(
                        creator_url=HttpUrl(builder_url),
                        editor_url=HttpUrl("http://editor.test"),
                        _env_file=None,
                    ),
                    selector=FixedSelector("create"),
                    http_client=downstream,
                )
                async with router_app.router.lifespan_context(router_app):
                    async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=router_app),
                        base_url="http://router.test",
                        headers={"A2A-Version": "1.0"},
                    ) as client:
                        response = await client.post(
                            "/",
                            json={
                                "jsonrpc": "2.0",
                                "id": "builder-integration",
                                "method": "SendMessage",
                                "params": {
                                    "message": {
                                        "messageId": "builder-message",
                                        "role": "ROLE_USER",
                                        "parts": [
                                            {"text": " Create a deck "},
                                            {"text": "about sales."},
                                            {"filename": "source.json", "raw": "e30="},
                                        ],
                                    }
                                },
                            },
                        )

        assert response.status_code == 200
        envelope = response.json()
        assert "error" not in envelope, envelope
        message = envelope["result"]["message"]
        assert message["parts"] == [
            {
                "data": {
                    "status": "placeholder",
                    "request": " Create a deck \nabout sales.",
                    "message": "Deck generation is not implemented. No presentation was created.",
                },
                "mediaType": "application/json",
            }
        ]
        assert "task" not in envelope["result"]
        assert decode_id(message["contextId"])[0] == "create"

    asyncio.run(run())
