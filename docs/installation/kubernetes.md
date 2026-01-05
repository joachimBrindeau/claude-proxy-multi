# Kubernetes Installation Guide

This guide covers deploying Claude Code Proxy to Kubernetes using Helm charts.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Accessing the Application](#accessing-the-application)
- [Adding Claude Accounts](#adding-claude-accounts)
- [Persistence](#persistence)
- [Ingress & TLS](#ingress--tls)
- [Monitoring & Health Checks](#monitoring--health-checks)
- [Scaling](#scaling)
- [Upgrading](#upgrading)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

## Prerequisites

Before you begin, ensure you have:

- Kubernetes cluster (v1.19+)
- `kubectl` configured to access your cluster
- Helm 3.x installed
- (Optional) cert-manager for automatic TLS certificates
- (Optional) Ingress controller (nginx, traefik, etc.)

### Verify Prerequisites

```bash
# Check Kubernetes connection
kubectl cluster-info

# Check Helm version
helm version

# Check cert-manager (if using TLS)
kubectl get pods -n cert-manager
```

## Installation

### Add Helm Repository

```bash
# Add the Claude Code Proxy Helm repository
helm repo add claude-code-proxy https://joachimbrindeau.github.io/claude-proxy-multi

# Update your local Helm chart repository cache
helm repo update
```

### Install with Default Values

```bash
# Create a namespace for the deployment
kubectl create namespace claude-proxy

# Install the chart
helm install my-proxy claude-code-proxy/claude-code-proxy \
  --namespace claude-proxy
```

### Install with Custom Values

Create a `values.yaml` file:

```yaml
# values.yaml
replicaCount: 1

image:
  tag: "0.1.7"

service:
  type: LoadBalancer
  port: 8000

persistence:
  enabled: true
  size: 2Gi
  storageClass: "standard"

resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 512Mi

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: claude-proxy.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: claude-proxy-tls
      hosts:
        - claude-proxy.example.com
```

Install with custom values:

```bash
helm install my-proxy claude-code-proxy/claude-code-proxy \
  --namespace claude-proxy \
  --values values.yaml
```

## Configuration

### Environment Variables

All configuration is done through the `values.yaml` file. Key sections:

#### Server Configuration

```yaml
env:
  server:
    host: "0.0.0.0"
    port: 8000
    logLevel: INFO
```

#### Multi-Account Rotation

```yaml
env:
  rotation:
    accountsPath: "/data/accounts.json"
    enabled: true
    hotReload: true
```

#### OAuth Configuration

```yaml
env:
  oauth:
    redirectUri: "https://claude-proxy.example.com/callback"
```

#### Debug Settings

```yaml
env:
  debug:
    verboseApi: false
    verboseStreaming: false
    logRequests: false
```

### Resource Limits

```yaml
resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 100m
    memory: 256Mi
```

### Storage Configuration

```yaml
persistence:
  enabled: true
  storageClass: "fast-ssd"
  accessMode: ReadWriteOnce
  size: 5Gi
  # Use existing PVC
  existingClaim: "my-existing-pvc"
```

## Accessing the Application

### Get Service URL

Depending on your service type:

#### ClusterIP (default)

```bash
# Port forward to access locally
kubectl port-forward -n claude-proxy \
  svc/my-proxy-claude-code-proxy 8000:8000

# Access at http://localhost:8000
```

#### LoadBalancer

```bash
# Get external IP
kubectl get svc -n claude-proxy my-proxy-claude-code-proxy

# Wait for EXTERNAL-IP to be assigned
# Access at http://<EXTERNAL-IP>:8000
```

#### NodePort

```bash
# Get node port
export NODE_PORT=$(kubectl get svc -n claude-proxy \
  my-proxy-claude-code-proxy -o jsonpath='{.spec.ports[0].nodePort}')

export NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[0].address}')

echo "Access at http://$NODE_IP:$NODE_PORT"
```

#### Ingress

```bash
# If ingress is enabled, access at your configured host
curl https://claude-proxy.example.com/health
```

## Adding Claude Accounts

### Method 1: Web UI (Recommended)

1. Access the application URL
2. Navigate to the web interface
3. Use the OAuth flow to add Claude accounts
4. Accounts are automatically saved to `/data/accounts.json`

### Method 2: Manual accounts.json

Create `accounts.json` with your OAuth credentials:

```json
{
  "accounts": [
    {
      "id": "account-1",
      "email": "user@example.com",
      "oauth_token": {
        "access_token": "your-access-token",
        "refresh_token": "your-refresh-token",
        "expires_at": 1234567890,
        "subscription_type": "pro"
      }
    }
  ]
}
```

Copy to the pod:

```bash
# Get pod name
POD_NAME=$(kubectl get pods -n claude-proxy \
  -l app.kubernetes.io/name=claude-code-proxy \
  -o jsonpath='{.items[0].metadata.name}')

# Copy accounts.json to pod
kubectl cp accounts.json \
  claude-proxy/$POD_NAME:/data/accounts.json

# Verify
kubectl exec -n claude-proxy $POD_NAME -- \
  cat /data/accounts.json
```

### Method 3: Init Container

Add an init container to your values:

```yaml
initContainers:
  - name: init-accounts
    image: busybox:latest
    command:
      - sh
      - -c
      - |
        if [ ! -f /data/accounts.json ]; then
          echo '{"accounts":[]}' > /data/accounts.json
        fi
    volumeMounts:
      - name: data
        mountPath: /data
```

## Persistence

### Enable Persistence

```yaml
persistence:
  enabled: true
  size: 1Gi
  storageClass: ""  # Use default storage class
```

### Use Existing PVC

```yaml
persistence:
  enabled: true
  existingClaim: "my-accounts-pvc"
```

### Disable Persistence (Testing Only)

```yaml
persistence:
  enabled: false
```

**Warning**: Disabling persistence will lose all accounts on pod restart.

## Ingress & TLS

### Basic Ingress

```yaml
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: claude-proxy.example.com
      paths:
        - path: /
          pathType: Prefix
```

### Ingress with TLS (cert-manager)

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "0"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "600"
  hosts:
    - host: claude-proxy.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: claude-proxy-tls
      hosts:
        - claude-proxy.example.com
```

### Manual TLS Secret

```bash
# Create TLS secret
kubectl create secret tls claude-proxy-tls \
  --namespace claude-proxy \
  --cert=path/to/cert.pem \
  --key=path/to/key.pem
```

## Monitoring & Health Checks

### Health Check Endpoints

The application provides three health endpoints:

- `/health/live` - Liveness probe (process running)
- `/health/ready` - Readiness probe (ready for traffic)
- `/health` - Detailed diagnostics

### Check Health Status

```bash
# Get pod name
POD_NAME=$(kubectl get pods -n claude-proxy \
  -l app.kubernetes.io/name=claude-code-proxy \
  -o jsonpath='{.items[0].metadata.name}')

# Check liveness
kubectl exec -n claude-proxy $POD_NAME -- \
  curl -s http://localhost:8000/health/live | jq

# Check readiness
kubectl exec -n claude-proxy $POD_NAME -- \
  curl -s http://localhost:8000/health/ready | jq

# Detailed health
kubectl exec -n claude-proxy $POD_NAME -- \
  curl -s http://localhost:8000/health | jq
```

### View Logs

```bash
# Tail logs
kubectl logs -n claude-proxy -f deployment/my-proxy-claude-code-proxy

# Last 100 lines
kubectl logs -n claude-proxy deployment/my-proxy-claude-code-proxy --tail=100

# Previous instance logs
kubectl logs -n claude-proxy deployment/my-proxy-claude-code-proxy --previous
```

### Prometheus Metrics (if enabled)

```yaml
metrics:
  enabled: true
  serviceMonitor:
    enabled: true
    interval: 30s
    scrapeTimeout: 10s
```

## Scaling

### Horizontal Pod Autoscaling

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80
  targetMemoryUtilizationPercentage: 80
```

Apply:

```bash
helm upgrade my-proxy claude-code-proxy/claude-code-proxy \
  --namespace claude-proxy \
  --set autoscaling.enabled=true \
  --set autoscaling.minReplicas=2 \
  --set autoscaling.maxReplicas=10
```

### Manual Scaling

```bash
# Scale to 3 replicas
kubectl scale deployment -n claude-proxy \
  my-proxy-claude-code-proxy --replicas=3
```

### Pod Disruption Budget

```yaml
podDisruptionBudget:
  enabled: true
  minAvailable: 1
```

## Upgrading

### Upgrade to Latest Version

```bash
# Update Helm repository
helm repo update

# Upgrade release
helm upgrade my-proxy claude-code-proxy/claude-code-proxy \
  --namespace claude-proxy \
  --values values.yaml
```

### Upgrade to Specific Version

```bash
helm upgrade my-proxy claude-code-proxy/claude-code-proxy \
  --namespace claude-proxy \
  --version 0.2.0 \
  --values values.yaml
```

### Rollback

```bash
# View release history
helm history my-proxy -n claude-proxy

# Rollback to previous version
helm rollback my-proxy -n claude-proxy

# Rollback to specific revision
helm rollback my-proxy 2 -n claude-proxy
```

## Troubleshooting

### Pod Not Starting

```bash
# Describe pod
kubectl describe pod -n claude-proxy -l app.kubernetes.io/name=claude-code-proxy

# Check events
kubectl get events -n claude-proxy --sort-by='.lastTimestamp'

# Check logs
kubectl logs -n claude-proxy -l app.kubernetes.io/name=claude-code-proxy
```

### PVC Issues

```bash
# Check PVC status
kubectl get pvc -n claude-proxy

# Describe PVC
kubectl describe pvc -n claude-proxy my-proxy-claude-code-proxy-data

# Check if storage class exists
kubectl get storageclass
```

### Service Not Accessible

```bash
# Check service
kubectl get svc -n claude-proxy my-proxy-claude-code-proxy

# Check endpoints
kubectl get endpoints -n claude-proxy my-proxy-claude-code-proxy

# Test from another pod
kubectl run test-pod -n claude-proxy --rm -it --image=curlimages/curl -- \
  curl http://my-proxy-claude-code-proxy:8000/health
```

### Ingress Not Working

```bash
# Check ingress
kubectl get ingress -n claude-proxy

# Describe ingress
kubectl describe ingress -n claude-proxy my-proxy-claude-code-proxy

# Check ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller
```

### OAuth Callback Issues

If OAuth callbacks fail, ensure `CCPROXY_OAUTH_REDIRECT_URI` matches your ingress host:

```yaml
env:
  oauth:
    redirectUri: "https://claude-proxy.example.com/callback"
```

### Data Persistence Issues

```bash
# Check if data directory is writable
POD_NAME=$(kubectl get pods -n claude-proxy \
  -l app.kubernetes.io/name=claude-code-proxy \
  -o jsonpath='{.items[0].metadata.name}')

kubectl exec -n claude-proxy $POD_NAME -- \
  sh -c 'touch /data/test && rm /data/test && echo "Writable"'

# Check file ownership
kubectl exec -n claude-proxy $POD_NAME -- \
  ls -la /data
```

## Uninstallation

### Delete Release

```bash
# Uninstall the Helm release
helm uninstall my-proxy -n claude-proxy
```

### Delete PVC (Optional)

```bash
# PVC is not automatically deleted
kubectl delete pvc -n claude-proxy my-proxy-claude-code-proxy-data
```

### Delete Namespace

```bash
# Delete entire namespace
kubectl delete namespace claude-proxy
```

## Advanced Configuration

### Network Policies

```yaml
networkPolicy:
  enabled: true
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: my-app
  egress:
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: TCP
          port: 443
```

### Custom Init Containers

```yaml
initContainers:
  - name: wait-for-db
    image: busybox:latest
    command: ['sh', '-c', 'until nc -z db-service 5432; do sleep 1; done']
```

### Sidecar Containers

```yaml
extraContainers:
  - name: log-forwarder
    image: fluent/fluent-bit:latest
    volumeMounts:
      - name: logs
        mountPath: /var/log
```

### Additional Volumes

```yaml
extraVolumes:
  - name: config
    configMap:
      name: my-config

extraVolumeMounts:
  - name: config
    mountPath: /config
    readOnly: true
```

## Production Best Practices

1. **Enable Persistence**: Always use persistent storage in production
2. **Resource Limits**: Set appropriate CPU/memory limits
3. **Health Checks**: Keep default health check settings
4. **TLS**: Use HTTPS with valid certificates
5. **Backups**: Regularly backup `/data/accounts.json`
6. **Monitoring**: Enable metrics and set up alerts
7. **Pod Disruption Budget**: Ensure high availability
8. **Network Policies**: Restrict traffic to necessary connections
9. **Security Context**: Run as non-root user (default)
10. **Update Strategy**: Use RollingUpdate for zero-downtime updates

## Example Production Values

```yaml
# production-values.yaml
replicaCount: 3

image:
  registry: ghcr.io
  repository: joachimbrindeau/claude-proxy-multi
  tag: "0.1.7"
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8000

persistence:
  enabled: true
  storageClass: "fast-ssd"
  size: 5Gi

resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 75

podDisruptionBudget:
  enabled: true
  minAvailable: 2

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: "0"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
  hosts:
    - host: claude-proxy.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: claude-proxy-tls
      hosts:
        - claude-proxy.example.com

env:
  server:
    logLevel: INFO
  rotation:
    enabled: true
    hotReload: true
  oauth:
    redirectUri: "https://claude-proxy.example.com/callback"
  debug:
    verboseApi: false

metrics:
  enabled: true
  serviceMonitor:
    enabled: true
    interval: 30s

networkPolicy:
  enabled: true
  policyTypes:
    - Ingress
    - Egress
```

Deploy:

```bash
helm install my-proxy claude-code-proxy/claude-code-proxy \
  --namespace claude-proxy \
  --values production-values.yaml
```

## Support

For issues and questions:

- GitHub Issues: https://github.com/joachimbrindeau/claude-proxy-multi/issues
- Documentation: https://github.com/joachimbrindeau/claude-proxy-multi/tree/main/docs
- Helm Chart: https://joachimbrindeau.github.io/claude-proxy-multi
