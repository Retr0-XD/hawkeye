// Builds resource-type-specific Google Cloud Console deep links so "Open in
// Console" lands on the actual resource, not just the project dashboard.

export function consoleUrlForResource(
  resourceId: string,
  type?: string,
  projectId: string = "dice-master-the-platform"
): string {
  const base = "https://console.cloud.google.com";
  // resourceId looks like: gcp://run/PROJECT/NAME, gcp://storage/PROJECT/NAME, etc.
  const parts = resourceId.split("/").filter(Boolean); // ["gcp:", "run", "PROJECT", "NAME"]
  const name = parts[parts.length - 1] ?? "";
  const proj = parts[2] ?? projectId;

  switch (type) {
    case "Container": // Cloud Run
      return `${base}/run/detail/${name}/revisions?project=${proj}`;
    case "Function":
      return `${base}/functions/details/${name}?project=${proj}&tab=trigger`;
    case "Database": // Cloud SQL
      return `${base}/sql/instances/${name}/overview?project=${proj}`;
    case "Storage": // Cloud Storage bucket
      return `${base}/storage/browser/${name}?project=${proj}`;
    case "Network": // VPC / subnet / LB — fall back to VPC list
      return `${base}/networking/addresses/list?project=${proj}`;
    case "Compute": // GCE VM
      return `${base}/compute/instancesDetail/zones/-/instances/${name}?project=${proj}`;
    case "Container-cluster": // GKE
      return `${base}/kubernetes/clusters/details/${name}/details?project=${proj}`;
    default:
      return `${base}/home/dashboard?project=${proj}`;
  }
}
