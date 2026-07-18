"""Resource collector (Layer 1, operation 1).

Fetches every supported GCP resource type for a project and normalizes them
into :class:`Resource` records. Handles pagination and aggregates per-API
errors so one failing API never aborts the whole ingestion run.

Supported types:
  - Compute Engine VMs (per zone)
  - Cloud Storage buckets
  - GKE clusters
  - Cloud SQL instances (Discovery API)
  - Cloud Run services (Discovery API)
  - Cloud Functions (Discovery API, v1/v2)
  - VPC networks / subnetworks / forwarding rules (load balancers)
  - Artifact Registry repositories (Discovery API)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List

from ..gcp_clients import (
    get_compute_client,
    get_compute_forwarding_rules_client,
    get_compute_networks_client,
    get_compute_subnetworks_client,
    get_container_client,
    get_discovery_resource,
    get_storage_client,
)
from ..models import Resource
from .base import gather_with_concurrency, is_error, ok_results

logger = logging.getLogger("hawkeye.ingestion.collectors.resources")


def _now_iso() -> datetime:
    return datetime.now(timezone.utc)


def _parse_gke_time(cluster) -> "datetime | None":
    """GKE create_time may be a Timestamp proto or an ISO string."""
    ct = getattr(cluster, "create_time", None)
    if ct is None:
        return None
    # Timestamp proto
    if hasattr(ct, "seconds"):
        if ct.seconds:
            return datetime.fromtimestamp(ct.seconds, tz=timezone.utc)
        return None
    # ISO string
    if isinstance(ct, str):
        try:
            return datetime.fromisoformat(ct.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def _collect_compute_vms(project_id: str) -> List[Resource]:
    client = get_compute_client()
    resources: List[Resource] = []

    # Discover zones first.
    from google.cloud import compute_v1

    zones_client = compute_v1.ZonesClient()
    zones = [z.name for z in zones_client.list(project=project_id)]

    async def _zone(zone: str) -> List[Resource]:
        out: List[Resource] = []
        try:
            # InstancesClient.list is sync + paginated; wrap in thread.
            loop = asyncio.get_event_loop()
            for inst in await loop.run_in_executor(
                None, lambda: client.list(project=project_id, zone=zone)
            ):
                created = None
                if inst.creation_timestamp:
                    created = datetime.fromisoformat(
                        inst.creation_timestamp.replace("Z", "+00:00")
                    )
                out.append(
                    Resource(
                        id=f"gcp://compute/{project_id}/{zone}/{inst.name}",
                        name=inst.name,
                        type="VM",
                        gcp_project_id=project_id,
                        provider_id=str(inst.id) if inst.id else None,
                        region=zone.rsplit("-", 1)[0] if "-" in zone else None,
                        zone=zone,
                        status="ACTIVE" if inst.status == "RUNNING" else inst.status,
                        created_at=created,
                        labels=dict(inst.labels or {}),
                        description=inst.description or None,
                        encryption_status="ENCRYPTED" if inst.disks else None,
                        public_access=any(
                            ac.get("name") == "External NAT"
                            for ac in (inst.access_configs or [])
                        ),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("compute.list zone=%s failed: %s", zone, exc)
            return exc
        return out

    results = await gather_with_concurrency(8, [_zone(z) for z in zones])
    for r in ok_results(results):
        resources.extend(r)
    return resources


def _bucket_is_public(bucket) -> bool:
    """A bucket is only public if it has an allUsers/allAuthenticatedUsers IAM
    binding or a public object ACL. PAP 'inherited' does NOT mean public."""
    try:
        policy = bucket.get_iam_policy()
        for binding in policy.get("bindings", []):
            for member in binding.get("members", []):
                if member in ("allUsers", "allAuthenticatedUsers"):
                    return True
    except Exception:  # noqa: BLE001
        pass
    # Fall back to legacy object ACLs on the bucket itself.
    try:
        for entry in bucket.acl:
            if entry.get("entity") in ("allUsers", "allAuthenticatedUsers"):
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


async def _collect_storage_buckets(project_id: str) -> List[Resource]:
    client = get_storage_client()
    out: List[Resource] = []
    try:
        loop = asyncio.get_event_loop()
        buckets = await loop.run_in_executor(None, lambda: list(client.list_buckets()))
        for b in buckets:
            out.append(
                Resource(
                    id=f"gcp://storage/{project_id}/{b.name}",
                    name=b.name,
                    type="Storage",
                    gcp_project_id=project_id,
                    region=b.location or None,
                    status="ACTIVE",
                    created_at=b.time_created,
                    public_access=_bucket_is_public(b),
                    encryption_status="ENCRYPTED" if getattr(b, "encryption", None) else None,
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("storage.list failed: %s", exc)
        return exc
    return out


async def _collect_gke_clusters(project_id: str) -> List[Resource]:
    client = get_container_client()
    out: List[Resource] = []
    try:
        loop = asyncio.get_event_loop()
        parent = f"projects/{project_id}/locations/-"
        clusters = await loop.run_in_executor(
            None, lambda: list(client.list_clusters(parent=parent).clusters)
        )
        for c in clusters:
            out.append(
                Resource(
                    id=f"gcp://gke/{project_id}/{c.name}",
                    name=c.name,
                    type="Cluster",
                    gcp_project_id=project_id,
                    region=c.location or None,
                    status="ACTIVE",
                    created_at=_parse_gke_time(c),
                    labels=dict(c.resource_labels or {}),
                    encryption_status="ENCRYPTED" if getattr(c, "cluster_encryption_config", None) else None,
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("gke.list failed: %s", exc)
        return exc
    return out


async def _collect_discovery(project_id: str) -> List[Resource]:
    """Cloud SQL, Cloud Run, Cloud Functions, Artifact Registry via Discovery."""
    out: List[Resource] = []
    sql = get_discovery_resource("sqladmin", "v1")
    run = get_discovery_resource("run", "v2")
    functions = get_discovery_resource("cloudfunctions", "v2")
    ar = get_discovery_resource("artifactregistry", "v1")

    # Cloud SQL
    if sql:
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: sql.instances().list(project=project_id).execute(),
            )
            for item in resp.get("items", []):
                out.append(
                    Resource(
                        id=f"gcp://cloudsql/{project_id}/{item['name']}",
                        name=item["name"],
                        type="Database",
                        gcp_project_id=project_id,
                        region=item.get("region"),
                        status=item.get("state", "ACTIVE"),
                        created_at=None,
                        labels=item.get("settings", {}).get("userLabels", {}),
                        encryption_status="ENCRYPTED"
                        if item.get("diskEncryptionConfiguration") else None,
                        backup_enabled=bool(item.get("settings", {}).get("backupConfiguration", {}).get("enabled")),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("cloudsql.list failed: %s", exc)

    # Cloud Run services
    if run:
        try:
            loop = asyncio.get_event_loop()
            parent = f"projects/{project_id}/locations/-"
            resp = await loop.run_in_executor(
                None, lambda: run.projects().locations().services().list(parent=parent).execute()
            )
            for item in resp.get("services", resp.get("items", [])):
                name = item["name"].split("/")[-1]
                # Cloud Run v2 surfaces status fields at the top level of the
                # service object (not under "status"). A service that has a uri
                # or a latestReadyRevision is serving -> ACTIVE. A terminal
                # condition in a failed state -> FAILED.
                _tc = item.get("terminalCondition") or {}
                _run_status = "ACTIVE"
                if _tc.get("state") == "CONDITION_FAILED":
                    _run_status = "FAILED"
                elif not item.get("uri") and not item.get("latestReadyRevision"):
                    _run_status = "PROVISIONING"
                # Region lives in the resource name path; labels under template.
                _region = item.get("region")
                if not _region:
                    _parts = item["name"].split("/")
                    if "locations" in _parts:
                        _region = _parts[_parts.index("locations") + 1]
                _labels = item.get("labels") or (item.get("template", {}) or {}).get(
                    "labels", {}
                )
                out.append(
                    Resource(
                        id=f"gcp://run/{project_id}/{name}",
                        name=name,
                        type="Container",
                        gcp_project_id=project_id,
                        region=_region,
                        status=_run_status,
                        labels=_labels,
                        created_at=item.get("createTime"),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("cloudrun.list failed: %s", exc)

    # Cloud Functions v2
    if functions:
        try:
            loop = asyncio.get_event_loop()
            parent = f"projects/{project_id}/locations/-"
            resp = await loop.run_in_executor(
                None, lambda: functions.projects().locations().functions().list(parent=parent).execute()
            )
            for item in resp.get("functions", []):
                name = item["name"].split("/")[-1]
                out.append(
                    Resource(
                        id=f"gcp://function/{project_id}/{name}",
                        name=name,
                        type="Function",
                        gcp_project_id=project_id,
                        region=item.get("location"),
                        status=item.get("state", "ACTIVE"),
                        labels=item.get("labels", {}),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("cloudfunctions.list failed: %s", exc)

    # Artifact Registry repositories
    if ar:
        try:
            loop = asyncio.get_event_loop()
            from google.cloud import compute_v1 as _cv1

            regions = [r.name for r in _cv1.RegionsClient().list(project=project_id)]
            for region in regions:
                parent = f"projects/{project_id}/locations/{region}"
                try:
                    resp = await loop.run_in_executor(
                        None,
                        lambda p=parent: ar.projects().locations().repositories().list(
                            parent=p, pageSize=100
                        ).execute(),
                    )
                except Exception:
                    continue
                for item in resp.get("repositories", []):
                    name = item["name"].split("/")[-1]
                    out.append(
                        Resource(
                            id=f"gcp://artifactrepo/{project_id}/{name}",
                            name=name,
                            type="Container",
                            gcp_project_id=project_id,
                            region=item.get("location"),
                            status="ACTIVE",
                            labels=item.get("labels", {}),
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("artifactregistry.list failed: %s", exc)

    return out


async def _collect_networking(project_id: str) -> List[Resource]:
    """VPC networks, subnetworks and forwarding rules (load balancers)."""
    out: List[Resource] = []
    nets = get_compute_networks_client()
    subs = get_compute_subnetworks_client()
    fwd = get_compute_forwarding_rules_client()
    try:
        loop = asyncio.get_event_loop()
        for n in await loop.run_in_executor(None, lambda: list(nets.list(project=project_id))):
            out.append(
                Resource(
                    id=f"gcp://network/{project_id}/{n.name}",
                    name=n.name,
                    type="Network",
                    gcp_project_id=project_id,
                    status="ACTIVE",
                    labels=dict(getattr(n, "labels", {}) or {}),
                )
            )
        # Subnetworks are scoped per region; list across all regions.
        from google.cloud import compute_v1 as _cv1

        regions = [r.name for r in _cv1.RegionsClient().list(project=project_id)]
        for region in regions:
            for s in await loop.run_in_executor(
                None, lambda r=region: list(subs.list(project=project_id, region=r))
            ):
                out.append(
                    Resource(
                        id=f"gcp://subnet/{project_id}/{s.name}",
                        name=s.name,
                        type="Network",
                        gcp_project_id=project_id,
                        region=s.region.rsplit("/", 1)[-1] if s.region else None,
                        status="ACTIVE",
                    )
                )
        for region in regions:
            for f in await loop.run_in_executor(
                None, lambda r=region: list(fwd.list(project=project_id, region=r))
            ):
                out.append(
                    Resource(
                        id=f"gcp://lb/{project_id}/{f.name}",
                        name=f.name,
                        type="Network",
                        gcp_project_id=project_id,
                        region=f.region.rsplit("/", 1)[-1] if f.region else None,
                        status="ACTIVE",
                        public_access=bool(f.load_balancing_scheme == "EXTERNAL"),
                    )
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("networking.list failed: %s", exc)
        return exc
    return out


async def collect_resources(project_id: str) -> List[Resource]:
    """Run all resource collectors concurrently and aggregate results."""
    results = await asyncio.gather(
        _collect_compute_vms(project_id),
        _collect_storage_buckets(project_id),
        _collect_gke_clusters(project_id),
        _collect_discovery(project_id),
        _collect_networking(project_id),
        return_exceptions=True,
    )
    resources: List[Resource] = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("Resource collector crashed: %s", r)
            continue
        if isinstance(r, list):
            resources.extend(r)
    logger.info("Collected %d resources for project %s", len(resources), project_id)
    return resources
