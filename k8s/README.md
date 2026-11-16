# Kubernetes

```
k8s/
  cluster/minikube/      once per cluster: Gateway API, Envoy Gateway and the Gateway, Argo CD, the metrics-server
  base/                  the app and Keycloak, shared by every environment
  components/minikube/   what an environment gets on the local cluster: PostgreSQL, Redis, Mailpit, fixed passwords
  overlays/staging/      follows develop
  overlays/production/   runs the released versions
  monitoring/            Prometheus, Alertmanager and Grafana: the chart's settings, CineCloud's alerts and dashboard
  apps/minikube/         the Argo CD Applications that deploy both overlays and monitoring
```

## Environments

Both run on the same cluster, each in a namespace of its own with its own
PostgreSQL, Redis, Keycloak and Mailpit: nothing done in staging touches the
data or the accounts of production.

|            | staging                          | production             |
| ---------- | -------------------------------- | ---------------------- |
| Address    | http://staging.localhost         | http://localhost       |
| Namespace  | `cinecloud-staging`              | `cinecloud-production` |
| Deployed   | from `develop`                   | from `main`            |
| Runs       | every tested commit of `develop` | released versions      |
| Image tags | `sha-<commit>`                   | `v<version>`           |
| Backend    | one pod                          | two to four pods       |

CI writes the image tags, into `overlays/staging/images/` after a push to
`develop` and into `overlays/production/images/` after a release; the README
at the top of the repository has the whole way from a commit to production.

To go back to the version before, set its tag in
`overlays/production/images/` on `develop` and merge that into `main`. That
works as long as the newer version brought no migration with it: the older
image does not know the newer schema. Otherwise the way is forward, with a
fix and a new version.

## Minikube

### Once per cluster

```sh
# an environment takes about 1 GB, most of it Keycloak, and so does the
# monitoring stack; all in all the cluster uses 5.5 GB
minikube start --cpus 4 --memory 8g
kubectl apply --server-side -k k8s/cluster/minikube
kubectl wait --timeout=5m -n envoy-gateway-system deployment/envoy-gateway --for=condition=Available
kubectl wait --timeout=5m -n argocd deployment --all --for=condition=Available
```

### Passwords

There are none to make: `components/minikube/kustomization.yml` brings fixed
ones for both environments, in plain text, and so does `monitoring/values.yml`
for Grafana. That is fine for a cluster that only this machine reaches, and
only for that.

### Deploy

Argo CD deploys from GitHub, not from the local checkout - staging from
`develop`, production and the monitoring stack from `main` - and creates the
namespaces. Hand it the two environments, and the monitoring stack along with
them (see *Monitoring* below):

```sh
kubectl apply -f k8s/apps/minikube
```

From then on there is nothing to run. Argo CD looks at both branches every
two to three minutes and syncs what changed: the migration first, then the
backend (see `base/migrate-job.yml` for the order).

```sh
kubectl -n argocd get applications          # SYNC STATUS and HEALTH
kubectl -n cinecloud-production get pods
kubectl -n cinecloud-staging get pods
```

### Autoscaling

In production the backend runs on two to four pods. Each gets half a core;
once they use more than 70 % of it on average, the HorizontalPodAutoscaler in
`base/backend.yml` starts another, and it takes one away again after five
quiet minutes. The CineCloud dashboard in Grafana shows the pods and their
CPU against both lines.

```sh
kubectl -n cinecloud-production get hpa backend    # TARGETS: CPU now / target, REPLICAS
```

Staging runs one pod of each and no autoscaler (`overlays/staging/small.yml`).
`loadtest/` puts production under the load that makes it scale.

### Argo CD

The web UI shows every resource of the apps, their sync history and the diff
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

Then open http://localhost for production or http://staging.localhost for
staging - not http://127.0.0.1: the Gateway answers to these two names only
(see `cluster/minikube/gateway.yml`), and passkeys need a domain name.
Browsers find every name ending in `.localhost` on this machine by
themselves. On its first start Keycloak takes about a minute before the
sign-in works.

### Keycloak

Each environment has its own, with its own accounts. The admin console is at
`/auth/admin` of the environment's address, user `admin`, password `admin`.

The realm `cinecloud` is imported from `base/cinecloud-realm.json` on the
first start only. The address it sends the browser back to after the sign-in
is a path there, `/admin/callback`, which Keycloak reads as relative to its
own address: each environment redirects to itself only, and the file is the
same for all.

Keycloak skips the import once the realm exists, so a later change to the
file has to be made in the console as well - or Keycloak starts over from the
file, which deletes every account of the realm:

```sh
kubectl -n cinecloud-staging exec postgres-0 -- psql -U cinecloud -d postgres -c 'DROP DATABASE keycloak WITH (FORCE)'
kubectl -n cinecloud-staging delete pod -l app.kubernetes.io/name=keycloak
```

Cinemas keep their data, but their admins' accounts are gone: each admin
registers again and has the new account linked to the cinema (see below).

The file lists all of Keycloak's required actions, since a list there replaces
Keycloak's own as a whole. The one change: every new account has to register
a passkey.

### Open a cinema

Admins have no password, only a passkey, and an account exists in one
environment only.

1. Open `/admin` of the environment, http://localhost/admin for production,
   choose *Register* on the sign-in page and enter an e-mail address and a
   name. The browser then creates the passkey, with Windows Hello, Touch ID
   or a phone.
2. The app asks for the cinema's name and its address on the visitor pages,
   and offers a week of demo programme to start with. Whoever opens a cinema
   manages it, and an account manages one cinema.

From then on the passkey signs the admin in, and `/admin` is where they add
halls and movies, plan showtimes and see what guests booked.

A further admin of an existing cinema registers the same way but opens no
cinema: the page that offers to open one shows the account's ID, which links
it instead:

```sh
kubectl -n cinecloud-production exec deploy/backend -- python -m scripts.add_admin --slug cineplex-bonn --user-id <ID>
```

Anyone who reaches the sign-in page can register and open a cinema, which
then appears on the start page. Where others can reach Keycloak, it would
verify e-mail addresses first, which takes a mail server.

### Mail

No mail leaves the cluster. Booking confirmations go to the Mailpit of their
environment, which keeps them and shows them at `/mail` of its address -
every guest's mail, whatever the address. The alerts of the monitoring stack
go to the one of production, http://localhost/mail. The mails are gone when
the pod restarts.

### Monitoring

One stack watches both environments. Its Application deploys the chart
kube-prometheus-stack into the namespace `monitoring`, with the settings in
`monitoring/values.yml`: Prometheus, which scrapes the cluster and the
`/metrics` of both backends; Alertmanager; and Grafana, which opens on the
CineCloud dashboard - traffic, bookings and resources, for the environment
chosen at its top - and has the chart's dashboards for Kubernetes beside it.
Like Argo CD, none of them is routed through the gateway:

```sh
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80     # http://localhost:3000, admin / local-only
kubectl -n monitoring port-forward svc/monitoring-prometheus 9090     # http://localhost:9090
kubectl -n monitoring port-forward svc/monitoring-alertmanager 9093   # http://localhost:9093
```

Alertmanager mails the alerts to Mailpit, addressed to ops@cinecloud.local:
the chart's for the cluster, and CineCloud's own in
`monitoring/alerts.yml` - a part of the app without a ready pod, server
errors, slow responses, Redis failing, confirmations not sent, an Argo CD app
that stays out of sync or unhealthy. They are worked out for each environment
on its own and name the one they are about. CI tests them against the cases
in `monitoring/alerts.test.yml`. The links in the mails lead to the
port-forwards above.

Prometheus keeps 15 days of metrics, at most 4 GB, on a volume that outlives
its pod.

### Stop and remove

```sh
minikube stop                                               # frees the memory, keeps everything
kubectl -n argocd delete application cinecloud-staging      # deletes the environment; its database stays
kubectl delete namespace cinecloud-staging                  # and that as well
kubectl -n argocd delete application monitoring             # the monitoring stack; its metrics stay
kubectl delete namespace monitoring                         # and those as well
```

Production goes the same way, with `cinecloud-production`.

Two things of the monitoring stack outlive its Application: the resource types
of the Prometheus Operator (CRDs), which Argo CD leaves in place, and the
service in kube-system through which the operator has Prometheus find the
kubelets, which the operator made itself:

```sh
kubectl delete crd $(kubectl api-resources --api-group=monitoring.coreos.com -o name)
kubectl -n kube-system delete service monitoring-kubelet
```

Deleting an environment with `kubectl delete -k` would not last: Argo CD puts
back whatever its Application still lists.
