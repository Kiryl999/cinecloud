# Kubernetes

```
k8s/
  cluster/minikube/    once per cluster: Gateway API, Envoy Gateway, Argo CD and the metrics-server
  base/                the app and Keycloak, shared by every environment
  overlays/minikube/   the local cluster: PostgreSQL, Redis, Mailpit, the Gateway, images from ghcr.io
  monitoring/          Prometheus, Alertmanager and Grafana: the chart's settings, CineCloud's alerts and dashboard
  apps/minikube/       the Argo CD Applications that deploy overlays/minikube and monitoring
```

## Minikube

### Once per cluster

```sh
# Keycloak alone takes about 700 MB, the monitoring stack about 1 GB
minikube start --cpus 4 --memory 8g
kubectl apply --server-side -k k8s/cluster/minikube
kubectl wait --timeout=5m -n envoy-gateway-system deployment/envoy-gateway --for=condition=Available
kubectl wait --timeout=5m -n argocd deployment --all --for=condition=Available
```

### Passwords

There are none to make: the overlay brings fixed ones, in plain text in
`overlays/minikube/kustomization.yml`, and so does `monitoring/values.yml` for
Grafana. That is fine for a cluster that only this machine reaches, and only
for that.

### Deploy

Argo CD deploys the app from main on GitHub, not from the local checkout,
and creates the namespace `cinecloud` for it. Hand it the app, and the
monitoring stack along with it (see *Monitoring* below):

```sh
kubectl apply -f k8s/apps/minikube
```

From then on there is nothing to run. CI builds both images after every push
to main, pushes them to ghcr.io and commits their tag to
`overlays/minikube/images/`. Argo CD looks at main every two to three minutes
and syncs what changed: the migration first, then the backend (see
`base/migrate-job.yml` for the order).

```sh
kubectl -n argocd get applications    # SYNC STATUS and HEALTH
kubectl -n cinecloud get pods
```

HEALTH stays *Progressing* until `minikube tunnel` runs: Argo CD counts the
Gateway as up only once it has an address.

### Autoscaling

The backend runs on two to four pods. Each gets half a core; once they use
more than 70 % of it on average, the HorizontalPodAutoscaler in
`base/backend.yml` starts another, and it takes one away again after five
quiet minutes. The CineCloud dashboard in Grafana shows the pods and their
CPU against both lines.

```sh
kubectl -n cinecloud get hpa backend    # TARGETS: CPU now / target, REPLICAS
```

`loadtest/` puts the app under the load that makes it scale.

### Argo CD

The web UI shows every resource of the app, its sync history and the diff
against git:

```sh
kubectl -n argocd port-forward svc/argocd-server 8443:443
```

Then open https://localhost:8443 (a self-signed certificate), user `admin`,
password:

```sh
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d
```

PowerShell has no `base64`:

```powershell
$b64 = kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}'
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
```

### Open the app

```sh
minikube tunnel    # in its own terminal; asks for sudo because of port 80
```

Then open http://localhost - not http://127.0.0.1: passkeys need a domain
name, and Keycloak only redirects back to the addresses its realm lists.
On its first start Keycloak takes about a minute before the sign-in works.

### Keycloak

The admin console is at http://localhost/auth/admin, user `admin`, password
`admin`.

The realm `cinecloud` is imported from `base/cinecloud-realm.json` on the
first start only. Keycloak skips the import once the realm exists, so a later
change to the file has to be made in the console as well - or Keycloak starts
over from the file, which deletes every account of the realm:

```sh
kubectl -n cinecloud exec postgres-0 -- psql -U cinecloud -d postgres -c 'DROP DATABASE keycloak WITH (FORCE)'
kubectl -n cinecloud delete pod -l app.kubernetes.io/name=keycloak
```

Cinemas keep their data, but their admins' accounts are gone: each admin
registers again and has the new account linked to the cinema (see below).

The file lists all of Keycloak's required actions, since a list there replaces
Keycloak's own as a whole. The one change: every new account has to register
a passkey.

### Open a cinema

Admins have no password, only a passkey.

1. Open http://localhost/admin, choose *Register* on the sign-in page and
   enter an e-mail address and a name. The browser then creates the passkey,
   with Windows Hello, Touch ID or a phone.
2. The app asks for the cinema's name and its address on the visitor pages,
   and offers a week of demo programme to start with. Whoever opens a cinema
   manages it, and an account manages one cinema.

From then on the passkey signs the admin in, and http://localhost/admin is
where they add halls and movies, plan showtimes and see what guests booked.

A further admin of an existing cinema registers the same way but opens no
cinema: the page that offers to open one shows the account's ID, which links
it instead:

```sh
kubectl -n cinecloud exec deploy/backend -- python -m scripts.add_admin --slug cineplex-bonn --user-id <ID>
```

Anyone who reaches the sign-in page can register and open a cinema, which
then appears on the start page. Where others can reach Keycloak, it would
verify e-mail addresses first, which takes a mail server.

### Mail

No mail leaves the cluster. Booking confirmations go to Mailpit, which keeps
them and shows them at http://localhost/mail - every guest's mail, whatever
the address, and the alerts of the monitoring stack. They are gone when its
pod restarts.

### Monitoring

The second Application deploys the chart kube-prometheus-stack into the
namespace `monitoring`, with the settings in `monitoring/values.yml`:
Prometheus, which scrapes the cluster and the backend's `/metrics`;
Alertmanager; and Grafana, which opens on the CineCloud dashboard - traffic,
bookings and resources - and has the chart's dashboards for Kubernetes beside
it. Like Argo CD, none of them is routed through the gateway:

```sh
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80     # http://localhost:3000, admin / local-only
kubectl -n monitoring port-forward svc/monitoring-prometheus 9090     # http://localhost:9090
kubectl -n monitoring port-forward svc/monitoring-alertmanager 9093   # http://localhost:9093
```

Alertmanager mails the alerts to Mailpit, addressed to ops@cinecloud.local:
the chart's for the cluster, and CineCloud's own in
`monitoring/alerts.yml` - a part of the app without a ready pod, server
errors, slow responses, Redis failing, confirmations not sent, an Argo CD app
that stays out of sync or unhealthy. CI tests them against the cases in
`monitoring/alerts.test.yml`. The links in the mails lead to the port-forwards
above.

Prometheus keeps 15 days of metrics, at most 4 GB, on a volume that outlives
its pod.

### Stop and remove

```sh
minikube stop                                    # frees the memory, keeps everything
kubectl -n argocd delete application cinecloud   # deletes the app; the database stays
kubectl delete namespace cinecloud               # and that as well
kubectl -n argocd delete application monitoring  # the monitoring stack; its metrics stay
kubectl delete namespace monitoring              # and those as well
```

Two things of the monitoring stack outlive its Application: the resource types
of the Prometheus Operator (CRDs), which Argo CD leaves in place, and the
service in kube-system through which the operator has Prometheus find the
kubelets, which the operator made itself:

```sh
kubectl delete crd $(kubectl api-resources --api-group=monitoring.coreos.com -o name)
kubectl -n kube-system delete service monitoring-kubelet
```

Deleting the app with `kubectl delete -k` would not last: Argo CD puts back
whatever its Application still lists.
