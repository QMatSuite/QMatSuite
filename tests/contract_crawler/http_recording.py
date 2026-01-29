"""
HTTP recording system for network-dependent RPC methods.

Records HTTP requests/responses to JSON cassettes for reproducible testing.
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict

# Try to import requests
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@dataclass
class RecordedRequest:
    """Recorded HTTP request."""
    method: str
    url: str
    headers: Dict[str, str]
    params: Dict[str, Any]
    data: Optional[Any] = None


@dataclass
class RecordedResponse:
    """Recorded HTTP response."""
    status_code: int
    headers: Dict[str, str]
    content: bytes
    encoding: Optional[str] = None


@dataclass
class RecordedExchange:
    """Recorded request/response exchange."""
    request: RecordedRequest
    response: RecordedResponse


class HTTPRecorder:
    """
    Records and replays HTTP requests.
    
    Cassettes are stored as JSON files in tests/fixtures/http_cassettes/.
    """
    
    def __init__(self, cassette_dir: Path):
        self.cassette_dir = cassette_dir
        self.cassette_dir.mkdir(parents=True, exist_ok=True)
        self.recordings: Dict[str, RecordedExchange] = {}
    
    def _cassette_path(self, method_name: str) -> Path:
        """Get cassette file path for a method."""
        return self.cassette_dir / f"{method_name}.json"
    
    def _request_key(self, method: str, url: str, params: Dict[str, Any]) -> str:
        """Generate a key for a request."""
        key_data = f"{method}:{url}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def record_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
    ) -> Optional[RecordedResponse]:
        """
        Record an HTTP request and return cached response if available.
        
        Returns:
            RecordedResponse if cached, None if needs to be fetched
        """
        params = params or {}
        headers = headers or {}
        
        key = self._request_key(method, url, params)
        cassette_path = self._cassette_path("network_requests")
        
        # Try to load existing cassette
        if cassette_path.exists():
            try:
                with open(cassette_path, 'rb') as f:
                    cassette = json.load(f)
                    if key in cassette:
                        exchange_data = cassette[key]
                        response_data = exchange_data["response"]
                        return RecordedResponse(
                            status_code=response_data["status_code"],
                            headers=response_data["headers"],
                            content=response_data["content"].encode() if isinstance(response_data["content"], str) else bytes(response_data["content"]),
                            encoding=response_data.get("encoding"),
                        )
            except Exception:
                pass  # If loading fails, proceed to record
        
        return None
    
    def save_response(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]],
        params: Optional[Dict[str, Any]],
        data: Optional[Any],
        response: requests.Response,
    ):
        """Save a request/response exchange to cassette."""
        params = params or {}
        headers = headers or {}
        
        key = self._request_key(method, url, params)
        cassette_path = self._cassette_path("network_requests")
        
        # Load existing cassette or create new
        cassette = {}
        if cassette_path.exists():
            try:
                with open(cassette_path, 'r') as f:
                    cassette = json.load(f)
            except Exception:
                pass
        
        # Record exchange
        exchange = RecordedExchange(
            request=RecordedRequest(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
            ),
            response=RecordedResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                content=response.content.decode('utf-8', errors='replace') if response.encoding else response.content.hex(),
                encoding=response.encoding,
            ),
        )
        
        # Convert to JSON-serializable dict
        exchange_dict = {
            "request": asdict(exchange.request),
            "response": {
                "status_code": exchange.response.status_code,
                "headers": exchange.response.headers,
                "content": exchange.response.content if isinstance(exchange.response.content, str) else exchange.response.content.hex(),
                "encoding": exchange.response.encoding,
            },
        }
        
        cassette[key] = exchange_dict
        
        # Save cassette
        with open(cassette_path, 'w') as f:
            json.dump(cassette, f, indent=2)
    
    def patch_requests(self):
        """
        Patch requests library to use recording.
        
        This is a simple monkey-patch that intercepts requests.get/post/etc.
        """
        if not REQUESTS_AVAILABLE:
            return
        
        original_get = requests.get
        original_post = requests.post
        
        def recorded_get(url, **kwargs):
            # Try to get from cache
            cached = self.record_request("GET", url, kwargs.get("headers"), kwargs.get("params"))
            if cached:
                # Create a mock response
                mock_response = requests.Response()
                mock_response.status_code = cached.status_code
                mock_response.headers = cached.headers
                mock_response._content = cached.content
                mock_response.encoding = cached.encoding or 'utf-8'
                return mock_response
            
            # Make real request
            response = original_get(url, **kwargs)
            
            # Save to cassette
            self.save_response("GET", url, kwargs.get("headers"), kwargs.get("params"), None, response)
            
            return response
        
        def recorded_post(url, **kwargs):
            cached = self.record_request("POST", url, kwargs.get("headers"), kwargs.get("params"), kwargs.get("data"))
            if cached:
                mock_response = requests.Response()
                mock_response.status_code = cached.status_code
                mock_response.headers = cached.headers
                mock_response._content = cached.content
                mock_response.encoding = cached.encoding or 'utf-8'
                return mock_response
            
            response = original_post(url, **kwargs)
            self.save_response("POST", url, kwargs.get("headers"), kwargs.get("params"), kwargs.get("data"), response)
            return response
        
        requests.get = recorded_get
        requests.post = recorded_post


# Global recorder instance
_cassette_dir = Path(__file__).parent.parent / "fixtures" / "http_cassettes"
_recorder = HTTPRecorder(_cassette_dir)


def enable_recording():
    """Enable HTTP recording for network-dependent methods."""
    _recorder.patch_requests()


def get_recorder() -> HTTPRecorder:
    """Get the global HTTP recorder instance."""
    return _recorder

