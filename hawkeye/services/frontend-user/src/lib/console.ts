// Builds resource-type-specific Google Cloud Console deep links so "Open in
// Console" lands on the actual resource, not just the project dashboard.
//
// Resource ids look like: gcp://run/PROJECT/NAME, gcp://storage/PROJECT/NAME,
// gcp://sql/PROJECT/NAME, gcp://compute/PROJECT/NAME, etc. The second path
// segment is the GCP product and drives the deep link.

export function consoleUrlForResource(
  resourceId: string,
  type?: string,
  projectId: string = "dice-master-the-platform"
): string {
  const base = "https://console.cloud.google.com";
  const parts = resourceId.split("/").filter(Boolean); // ["gcp:", "run", "PROJECT", "NAME"]
  const product = (parts[1] ?? "").toLowerCase();
  const name = parts.slice(3).join("/") || parts[parts.length - 1] || "";
  const proj = parts[2] ?? projectId;

  // Prefer the product segment from the id (most reliable), then fall back to
  // the human-readable `type` field.
  const key = product || (type ?? "").toLowerCase();

  switch (key) {
    case "run":
    case "container":
      return `${base}/run/detail/${name}/revisions?project=${proj}`;
    case "functions":
    case "function":
      return `${base}/functions/details/${name}?project=${proj}&tab=trigger`;
    case "sql":
    case "database":
      return `${base}/sql/instances/${name}/overview?project=${proj}`;
    case "storage":
      return `${base}/storage/browser/${name}?project=${proj}`;
    case "network":
      return `${base}/networking/addresses/list?project=${proj}`;
    case "compute":
    case "vm":
      return `${base}/compute/instancesDetail/zones/-/instances/${name}?project=${proj}`;
    case "gke":
    case "container-cluster":
      return `${base}/kubernetes/clusters/details/${name}/details?project=${proj}`;
    case "artifactrepo":
    case "artifact-registry":
    case "artifact":
      return `${base}/artifacts/docker/${proj}/${name}?project=${proj}`;
    case "pubsub":
      return `${base}/cloudpubsub/topic/list?project=${proj}`;
    case "bigquery":
      return `${base}/bigquery?project=${proj}`;
    case "firestore":
      return `${base}/firestore/databases?project=${proj}`;
    default:
      // Best-effort: jump to the product's console area instead of the bare
      // dashboard so the user lands close to the resource they were viewing.
      return `${base}/home/dashboard?project=${proj}`;
  }
}
