# Local Development Setup

This guide covers setting up the task management system on your local machine using minikube.

## Prerequisites

**Required Software:**

- Podman Desktop for macOS (latest version from https://podman-desktop.io/downloads)
- minikube (latest version from https://minikube.sigs.k8s.io/docs/start/)
- kubectl (compatible with your Kubernetes version)
- make
- Python 3.9+ (for local development/testing)

**System Requirements:**

- MacBook Pro M2 with 16GB RAM (or equivalent)
- At least 8GB RAM available for Podman machine and minikube
- 50GB free disk space for Podman machine

## Initial Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd task-management-k8s
```

### 2. Start minikube with Podman

```bash
# Ensure Podman Desktop is running and create/start Podman machine
# Recommended Podman machine settings:
# - CPUs: 4
# - Memory: 8GB  
# - Disk: 50GB
# - Provider: Apple HyperVisor (for M2 Macs)
# - Root privileges: Enabled

podman machine list
podman machine start podman-machine-default  # if not running

# Start minikube using podman driver (7GB fits within Podman machine limits)
minikube start --driver=podman --cpus=4 --memory=7168 --disk-size=20g

# Enable required addons
minikube addons enable metrics-server
minikube addons enable storage-provisioner

# Verify cluster is running
kubectl cluster-info
kubectl get nodes
```

### 3. Configure Container Environment

```bash
# Configure Docker CLI to use minikube's docker daemon
eval $(minikube docker-env)

# Verify configuration - you should see Kubernetes system containers
docker ps

# Verify environment variables are set
echo $DOCKER_HOST  # Should show tcp://127.0.0.1:<port>
```

## Final Verification

Your local development environment is fully configured when you see:

**Cluster Status:**

```bash
kubectl cluster-info
kubectl get nodes
# Should show minikube node in Ready state
```

**Container Access:**

```bash
docker ps
# Should show Kubernetes system containers (metrics-server, storage-provisioner, etc.)
```

**Environment Variables:**

```bash
echo $DOCKER_HOST
# Should show tcp://127.0.0.1:<port> pointing to minikube's Docker daemon
```

## Important Notes

**Terminal Session**: The `eval $(minikube docker-env)` command configures your current terminal session only. For new terminals, you'll need to run it again.

**No Local Docker Needed**: You don't need Docker Desktop installed. The Docker CLI connects to minikube's Docker daemon running inside your Podman container.

## Setup Complete

Your local development environment is ready for Phase 1 deployment. See `phase1-setup.md` for next steps.

## Development Workflow

### Build Container Images

```bash
# Build all container images locally
make build-local

# Verify images are built
podman images | grep task-mgmt
```

### Deploy System Components

Deploy the system progressively through phases:

```bash
# Phase 1: Database and basic API
make phase1

# Verify Phase 1 deployment
kubectl get pods -n task-mgmt
kubectl get services -n task-mgmt
```

### Access the System

**API Endpoint:**

- URL: `http://localhost:30080` (NodePort service)
- Test: `curl http://localhost:30080/health`

**Internal Services:** Use port-forwarding for database or internal service access:

```bash
# Access PostgreSQL directly (if needed)
kubectl port-forward -n task-mgmt svc/postgres 5432:5432
```

## Verification

### Check System Health

```bash
# All pods should be Running
kubectl get pods -n task-mgmt

# Services should have endpoints
kubectl get endpoints -n task-mgmt

# Check persistent volumes
kubectl get pv,pvc -n task-mgmt
```

### Test Basic Functionality

```bash
# Test API health endpoint
make test-basic

# Check application logs
kubectl logs -n task-mgmt -l app=api
kubectl logs -n task-mgmt -l app=postgres
```

## Common Issues and Solutions

### minikube Won't Start

```bash
# Delete existing cluster and restart with podman
minikube delete
minikube start --driver=podman --cpus=4 --memory=8192

# If podman driver issues, check podman is running
systemctl --user status podman.socket
systemctl --user start podman.socket
```

### Images Not Found

```bash
# Ensure podman environment is configured
eval $(minikube podman-env)

# Rebuild images
make build-local

# Check podman can access images
podman images
```

### Pods Stuck in Pending

```bash
# Check pod status and resource constraints
kubectl describe pod <pod-name> -n task-mgmt

# Check node resources
kubectl top nodes
kubectl describe node minikube
```

### Storage Issues

```bash
# Check storage class and persistent volumes
kubectl get storageclass
kubectl get pv,pvc -n task-mgmt

# If needed, recreate storage
kubectl delete pvc -n task-mgmt --all
```

## Development Commands

### Useful kubectl Commands

```bash
# Watch pod status
kubectl get pods -n task-mgmt -w

# Get all resources in namespace
kubectl get all -n task-mgmt

# Check resource usage
kubectl top pods -n task-mgmt
```

### Cleanup

```bash
# Remove all deployed resources
make clean-local

# Stop minikube (keeps the cluster)
minikube stop

# Delete minikube cluster completely
minikube delete
```

## Next Steps

After successful local setup:

1. Verify basic task creation through the API
2. Deploy Phase 2 components (workers and load generation)
3. Test scaling and resilience features
4. Move to AWS EKS deployment (see `aws-deployment.md`)

For testing procedures, see `testing.md`. For troubleshooting, see `troubleshooting.md`.