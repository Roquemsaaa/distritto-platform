import base64
import json
from dataclasses import dataclass
import httpx

API_VERSION = "2026-03-10"

@dataclass
class GitHubRepoClient:
    token: str
    owner: str
    repo: str
    branch: str

    @property
    def base_url(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repo}"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": API_VERSION,
        }

    async def _request(self, method: str, url: str, **kwargs):
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.request(method, url, headers=self.headers, **kwargs)
        if response.status_code >= 400:
            raise RuntimeError(f"GitHub {response.status_code}: {response.text[:500]}")
        return response

    async def read_text_file(self, path: str) -> str:
        response = await self._request(
            "GET",
            f"{self.base_url}/contents/{path}",
            params={"ref": self.branch},
        )
        data = response.json()
        raw = base64.b64decode(data["content"]).decode("utf-8")
        return raw

    async def _head(self) -> tuple[str, str]:
        ref = (await self._request("GET", f"{self.base_url}/git/ref/heads/{self.branch}")).json()
        commit_sha = ref["object"]["sha"]
        commit = (await self._request("GET", f"{self.base_url}/git/commits/{commit_sha}")).json()
        tree_sha = commit["tree"]["sha"]
        return commit_sha, tree_sha

    async def _create_blob(self, content: bytes) -> str:
        payload = {
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        }
        response = await self._request("POST", f"{self.base_url}/git/blobs", json=payload)
        return response.json()["sha"]

    async def commit_files(self, files: dict[str, bytes], message: str) -> str:
        parent_sha, base_tree_sha = await self._head()

        tree_entries = []
        for path, content in files.items():
            blob_sha = await self._create_blob(content)
            tree_entries.append({
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            })

        tree = (await self._request(
            "POST",
            f"{self.base_url}/git/trees",
            json={"base_tree": base_tree_sha, "tree": tree_entries},
        )).json()

        commit = (await self._request(
            "POST",
            f"{self.base_url}/git/commits",
            json={
                "message": message,
                "tree": tree["sha"],
                "parents": [parent_sha],
            },
        )).json()

        await self._request(
            "PATCH",
            f"{self.base_url}/git/refs/heads/{self.branch}",
            json={"sha": commit["sha"], "force": False},
        )
        return commit["sha"]
