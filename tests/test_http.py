import ssl
import unittest
import urllib.error

from gtfs_fr_pipeline.http import JsonClient, NotFound
from gtfs_fr_pipeline.source import ApiError

BASE = "https://transport.data.gouv.fr"
OK = (200, {}, b"[]")


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls: list[str] = []

    def __call__(self, url, timeout):
        self.urls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_client(responses, **kwargs):
    fake_clock = FakeClock()
    transport = FakeTransport(responses)
    client = JsonClient(BASE, transport=transport, sleep=fake_clock.sleep, clock=fake_clock.clock, **kwargs)
    return client, transport, fake_clock


class RetryAndPolitenessTest(unittest.TestCase):
    def test_url_and_params(self):
        client, transport, _ = make_client([OK])
        self.assertEqual(client.get_json("/api/datasets", {"type": "public-transit"}), [])
        self.assertEqual(transport.urls, [f"{BASE}/api/datasets?type=public-transit"])

    def test_retries_server_errors_then_succeeds(self):
        client, transport, clock = make_client([(503, {}, b""), (502, {}, b""), OK])
        self.assertEqual(client.get_json("/api/datasets"), [])
        self.assertEqual(len(transport.urls), 3)
        self.assertIn(1.0, clock.sleeps)  # backoff_base ** 0
        self.assertIn(2.0, clock.sleeps)  # backoff_base ** 1

    def test_honours_retry_after(self):
        client, _, clock = make_client([(429, {"Retry-After": "7"}, b""), OK])
        client.get_json("/api/datasets")
        self.assertIn(7.0, clock.sleeps)

    def test_retry_after_is_capped(self):
        client, _, clock = make_client([(429, {"retry-after": "3600"}, b""), OK], max_backoff=30)
        client.get_json("/api/datasets")
        self.assertIn(30.0, clock.sleeps)

    def test_network_errors_are_retried(self):
        client, transport, _ = make_client([ConnectionError("reset"), OK])
        client.get_json("/api/datasets")
        self.assertEqual(len(transport.urls), 2)

    def test_certificate_errors_are_not_retried(self):
        err = urllib.error.URLError(ssl.SSLCertVerificationError("unable to get local issuer certificate"))
        client, transport, _ = make_client([err, OK])
        with self.assertRaises(ApiError):
            client.get_json("/api/datasets")
        self.assertEqual(len(transport.urls), 1)

    def test_gives_up_after_max_retries(self):
        client, transport, _ = make_client([(503, {}, b"")] * 3, max_retries=2)
        with self.assertRaises(ApiError):
            client.get_json("/api/datasets")
        self.assertEqual(len(transport.urls), 3)

    def test_404_and_other_4xx_are_not_retried(self):
        client, transport, _ = make_client([(404, {}, b"")])
        with self.assertRaises(NotFound):
            client.get_json("/api/datasets/x")
        self.assertEqual(len(transport.urls), 1)
        client, transport, _ = make_client([(403, {}, b"")])
        with self.assertRaises(ApiError):
            client.get_json("/api/datasets")
        self.assertEqual(len(transport.urls), 1)

    def test_invalid_json_is_an_error(self):
        client, _, _ = make_client([(200, {}, b"<html>")])
        with self.assertRaises(ApiError):
            client.get_json("/api/datasets")

    def test_min_interval_between_requests(self):
        client, _, clock = make_client([OK, OK], min_interval=1.0)
        client.get_json("/api/datasets")
        clock.now += 0.25
        client.get_json("/api/datasets")
        self.assertEqual(clock.sleeps, [0.75])


if __name__ == "__main__":
    unittest.main()
