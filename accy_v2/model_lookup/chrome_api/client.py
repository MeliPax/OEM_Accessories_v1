"""
HTTP client for AutoData Solutions YMMT API.

Implements:
  - Basic auth from credentials
  - User-Agent rotation (from notebook pattern)
  - Retry/backoff via urllib3.Retry
  - Explicit timeout on every request
  - Proper error handling and logging
"""

import random
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.90 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0",
    "Mozilla/5.0 (iPad; CPU OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_6_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0",
]

# Request timeout in seconds (total time for connect + read)
REQUEST_TIMEOUT = 30

# Pacing delay between requests (seconds) — be a good API citizen
REQUEST_DELAY = 0.5


class ADSClient:
    """
    HTTP client for AutoData Solutions YMMT API.

    Handles authentication, retry/backoff, timeout, and User-Agent rotation.
    """

    def __init__(self, base_url: str, api_user: str, api_password: str):
        """
        Initialize ADS API client.

        Args:
            base_url: Base URL for ADS API (e.g. https://demos.autodatasolutions.com/ADSDemo)
            api_user: API username
            api_password: API password
        """
        self.base_url = base_url.rstrip("/")
        self.api_user = api_user
        self.api_password = api_password

        # Create session with retry strategy
        self.session = requests.Session()
        self._setup_retry_strategy()

    def _setup_retry_strategy(self):
        """Configure retry/backoff strategy on the session."""
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,  # 1s, 2s, 4s between retries
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on server errors + rate limit
            allowed_methods=["GET"],  # Only retry GET requests (idempotent)
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _get_headers(self) -> Dict[str, str]:
        """
        Build request headers with auth and rotating User-Agent.

        Returns:
            dict of HTTP headers
        """
        import base64

        # Basic auth: base64(user:password)
        auth_str = f"{self.api_user}:{self.api_password}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()

        return {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Authorization": f"Basic {auth_b64}",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Origin": "https://demos.autodatasolutions.com",
            "Referer": "https://demos.autodatasolutions.com/ADSDemo/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": random.choice(USER_AGENTS),
        }

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform GET request to ADS API.

        Args:
            endpoint: Path relative to base_url (e.g. "/api/ymmt/years/...")
            params: Query parameters (optional)

        Returns:
            Parsed JSON response as dict

        Raises:
            requests.exceptions.RequestException if the request fails
        """
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        try:
            response = self.session.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            # Handle empty responses
            if not response.text:
                print(f"[DEBUG] Empty response from {url}")
                print(f"[DEBUG] Status code: {response.status_code}")
                return {}

            result = response.json()
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Request failed for {url}")
            print(f"[DEBUG] Status code: {response.status_code if 'response' in locals() else 'N/A'}")
            if 'response' in locals() and response.text:
                print(f"[DEBUG] Response text: {response.text[:200]}")
            raise RuntimeError(f"ADS API request failed for {url}: {e}")
        finally:
            # Rate limiting: sleep after each request completes
            time.sleep(REQUEST_DELAY)

        return result

    def _post(self, endpoint: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform POST request to ADS API with JSON body.

        Args:
            endpoint: Path relative to base_url
            body: Request body as dict (will be JSON-encoded)

        Returns:
            Parsed JSON response as dict

        Raises:
            requests.exceptions.RequestException if the request fails
        """
        import json
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()

        try:
            response = self.session.post(
                url,
                headers=headers,
                data=json.dumps(body),
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            # Handle empty responses
            if not response.text:
                print(f"[DEBUG] Empty response from {url}")
                print(f"[DEBUG] Status code: {response.status_code}")
                return {}

            result = response.json()
        except requests.exceptions.RequestException as e:
            print(f"[DEBUG] Request failed for {url}")
            print(f"[DEBUG] Status code: {response.status_code if 'response' in locals() else 'N/A'}")
            if 'response' in locals() and response.text:
                print(f"[DEBUG] Response text: {response.text[:200]}")
            raise RuntimeError(f"ADS API request failed for {url}: {e}")
        finally:
            # Rate limiting: sleep after each request completes
            time.sleep(REQUEST_DELAY)

        return result

    def get_years(self, country: str, language: str, sort: str) -> list:
        """
        Fetch available model years.

        Args:
            country: Country code (e.g., "US")
            language: Language code (e.g., "en")
            sort: Sort order: "ASC" or "DESC"

        Returns:
            list of year integers
        """
        endpoint = f"/api/ymmt/years/country/{country}/language/{language}"
        params = {"sort": sort}
        response = self.get(endpoint, params)
        # API wraps years in a "years" key
        if isinstance(response, dict):
            return response.get("years", [])
        return response if isinstance(response, list) else []

    def get_makes(
        self, year: int, country: str, language: str, sort: str
    ) -> list:
        """
        Fetch makes (manufacturers) for a given year.

        Args:
            year: Model year
            country: Country code (e.g., "US")
            language: Language code (e.g., "en")
            sort: Sort order: "ASC" or "DESC"

        Returns:
            list of make names
        """
        endpoint = f"/api/ymmt/makes/year/{year}/country/{country}/language/{language}"
        params = {"sort": sort}
        response = self.get(endpoint, params)
        # API wraps makes in a "makes" key
        if isinstance(response, dict):
            return response.get("makes", [])
        return response if isinstance(response, list) else []

    def get_models(
        self, year: int, make: str, country: str, language: str, sort: str
    ) -> list:
        """
        Fetch models for a given year and make.

        Args:
            year: Model year
            make: Manufacturer name
            country: Country code (e.g., "US")
            language: Language code (e.g., "en")
            sort: Sort order: "ASC" or "DESC"

        Returns:
            list of model names
        """
        endpoint = f"/api/ymmt/models/make/{make}/year/{year}/country/{country}/language/{language}"
        params = {"sort": sort}
        response = self.get(endpoint, params)
        # API wraps models in a "models" key
        if isinstance(response, dict):
            return response.get("models", [])
        return response if isinstance(response, list) else []

    def get_trims(self, year: int, make: str, model: str, language_locale: str) -> Dict[str, Any]:
        """
        Fetch trim data (full YMMT) for a given year, make, and model.

        This is the endpoint that returns detailed trim/style/configuration data.
        Note: This endpoint requires POST (not GET) with languageLocale in request body.

        Args:
            year: Model year
            make: Manufacturer name
            model: Model name
            language_locale: Language locale (e.g., "CA_en", "US_en")

        Returns:
            dict with trim/configuration data from ADS
        """
        endpoint = f"/api/full/ymmt/year/{year}/make/{make}/model/{model}/"
        body = {"languageLocale": language_locale}
        response = self._post(endpoint, body)
        return response if isinstance(response, dict) else {}
