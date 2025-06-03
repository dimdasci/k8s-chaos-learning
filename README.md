# Phase 1 Quick Start

This guide shows how to deploy, test, and cleanup the Phase 1 task management system.

## Prerequisites

- minikube running with Docker driver
- kubectl configured to use minikube cluster
- Podman Desktop running (for macOS)

## Deploy

Deploy the complete Phase 1 system with a single command:

```bash
make quick-deploy
```

This will:
- Build the API Docker image
- Deploy PostgreSQL with persistent storage
- Deploy FastAPI service (2 replicas)
- Create NodePort service for external access

**Expected output:** All pods running, services created, endpoints ready.

## Test

### 1. Start API Access

In **Terminal 1**, start port forwarding:
```bash
make port-forward
```
Keep this terminal open.

### 2. Test Health Endpoint

In **Terminal 2**, test the API:
```bash
make test-health
```
**Expected:** `{"status":"healthy","service":"task-api"}`

### 3. Test Task Management

```bash
make test-tasks
```
**Expected:** 
- Task creation response with ID
- Task listing showing the created task

## Check Status

View all system components:
```bash
make status
```

View API logs:
```bash
make logs
```

## Cleanup

Remove all Phase 1 resources:
```bash
make clean-phase1
```

## Access Methods

| Method | Command | Use Case |
|--------|---------|----------|
| Port forwarding | `make port-forward` | Development, testing |
| Service tunnel | `make tunnel` | Browser access |
| Status check | `make status` | Monitor deployments |

## Troubleshooting

**Port forwarding fails:**
- Check pods are running: `make status`
- Check API logs: `make logs`

**Image build fails:**
- Ensure minikube is running: `minikube status`
- Configure Docker environment: `eval $(minikube docker-env)`

**Database connection issues:**
- Verify secret exists: `kubectl get secrets -n task-mgmt`
- Check PostgreSQL logs: `kubectl logs -n task-mgmt -l app=postgres`

## What's Next

Phase 1 provides the foundation with basic API and database functionality. Phase 2 will add:
- Worker pods for task processing
- Load generation for testing
- Horizontal pod autoscaling