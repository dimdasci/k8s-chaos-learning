# Phase 1 Setup: Basic System Deployment

## Overview

Phase 1 establishes the foundation of our task management system with core components running in minikube. We'll deploy a single PostgreSQL database with persistent storage and a minimal FastAPI service accessible via NodePort.

**What we're building:**

- PostgreSQL database with persistent volume
- FastAPI service for task creation
- NodePort service for external access
- Basic task creation functionality (no workers yet)

**What we're learning:**

- Kubernetes manifests (Deployment, Service, PersistentVolume)
- Database connectivity patterns
- External cluster access via NodePort
- Pod-to-pod communication basics

## Architecture for Phase 1

```
External → NodePort Service → API Service → API Pods → PostgreSQL Service → PostgreSQL Pod
  :30080      (port 8000)       (port 8000)    (port 5432)      (port 5432)
```

## Step 1: Namespace Setup

Working with your existing project structure:

```
.
├── Makefile
├── README.md
├── docker
│   ├── api
│   ├── load-generator
│   └── worker
├── docs
│   ├── Phase 1.md
│   └── local-setup.md
├── k8s
│   ├── base
│   │   ├── api
│   │   ├── database
│   │   ├── external
│   │   ├── load-generator
│   │   └── worker
│   └── overlays
│       ├── aws
│       └── local
└── scripts
    ├── aws
    ├── local
    └── shared
```

This structure follows Kustomize patterns with base manifests and environment-specific overlays, which is excellent for managing different deployments.

### Create Namespace

Create `k8s/base/namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: task-mgmt
  labels:
    app: task-management
    phase: "1"
```

Apply the namespace:

```bash
kubectl apply -f k8s/base/namespace.yaml
kubectl get namespaces
```

**Verification:** You should see `task-mgmt` namespace in Active state.

## Step 2: PostgreSQL Database Setup

Now we'll deploy PostgreSQL with persistent storage. This involves creating a PersistentVolume, PersistentVolumeClaim, and the PostgreSQL deployment.

**Why we need these components:** When a Kubernetes pod restarts or gets deleted, any data stored inside the container is lost. For a database, this would be catastrophic. To solve this, we use Kubernetes persistent storage. A PersistentVolume (PV) is like reserving actual disk space on the host machine, while a PersistentVolumeClaim (PVC) is your application's request to use that storage. Think of PV as the physical hard drive and PVC as your application saying "I need 5GB of storage please."

The PostgreSQL Deployment tells Kubernetes how to run our database container, including which Docker image to use, environment variables for database setup, and crucially, how to attach our persistent storage so data survives pod restarts. The Service creates a stable network endpoint that other pods can use to connect to the database, even if the actual PostgreSQL pod gets replaced.

### Create Database Manifests

**Security First:** We'll use Kubernetes Secrets to store database credentials instead of hardcoding them in the deployment manifest. This is a critical security practice you should always follow.

Create `k8s/base/database/postgres-secret.yaml.template`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: task-mgmt
  labels:
    app: postgres
type: Opaque
data:
  # Base64 encoded values: echo -n 'your-value' | base64
  # Replace these with your own base64-encoded credentials
  POSTGRES_DB: <base64-encoded-db-name>
  POSTGRES_USER: <base64-encoded-username>
  POSTGRES_PASSWORD: <base64-encoded-password>
```

**Setup your local secrets:**

```bash
# Copy the template and create your actual secret file
cp k8s/base/database/postgres-secret.yaml.template k8s/base/database/postgres-secret.yaml

# Generate base64 values for your credentials
echo -n 'taskdb' | base64      # Copy this to POSTGRES_DB
echo -n 'taskuser' | base64    # Copy this to POSTGRES_USER  
echo -n 'taskpass' | base64    # Copy this to POSTGRES_PASSWORD

# Edit the file and replace the placeholder values
# vim k8s/base/database/postgres-secret.yaml
```

**Add to .gitignore:**

```bash
# Add this line to your project root .gitignore file
echo "k8s/base/database/postgres-secret.yaml" >> .gitignore
```

Create `k8s/base/database/postgres-pv.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: postgres-pv
  labels:
    app: postgres
spec:
  capacity:
    storage: 5Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: standard
  hostPath:
    path: /mnt/data/postgres
```

Create `k8s/base/database/postgres-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: task-mgmt
  labels:
    app: postgres
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  storageClassName: standard
```

Create `k8s/base/database/postgres-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: task-mgmt
  labels:
    app: postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:16-alpine
        env:
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: POSTGRES_DB
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: POSTGRES_USER
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: POSTGRES_PASSWORD
        - name: PGDATA
          value: "/var/lib/postgresql/data/pgdata"
        ports:
        - containerPort: 5432
          name: postgres
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
```

Create `k8s/base/database/postgres-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: task-mgmt
  labels:
    app: postgres
spec:
  type: ClusterIP
  ports:
  - port: 5432
    targetPort: 5432
    name: postgres
  selector:
    app: postgres
```

### Deploy PostgreSQL

```bash
# Apply the secret first
kubectl apply -f k8s/base/database/postgres-secret.yaml

# Then apply all other database manifests
kubectl apply -f k8s/base/database/postgres-pv.yaml
kubectl apply -f k8s/base/database/postgres-pvc.yaml
kubectl apply -f k8s/base/database/postgres-deployment.yaml
kubectl apply -f k8s/base/database/postgres-service.yaml

# Verify deployment
kubectl get pods -n task-mgmt
kubectl get pv,pvc -n task-mgmt
kubectl get svc -n task-mgmt
kubectl get secrets -n task-mgmt
```

**Expected output:**

- Pod: `postgres-xxx` should be in Running state
- PVC: `postgres-pvc` should be Bound
- Service: `postgres` should have ClusterIP assigned

## Step 3: FastAPI Application

Now we'll create a minimal FastAPI application that can create tasks in our PostgreSQL database. We need to build a Docker image and deploy it to Kubernetes.

### Create FastAPI Application Structure

The FastAPI application includes:

- **User isolation** - All tasks are scoped to a `user_id`
- **Structured logging** - JSON formatted logs for better monitoring
- **Request context** - Each request gets a unique ID for tracing
- **Health checks** - Endpoint for Kubernetes health monitoring
- **Database initialization** - Automatic table creation and indexing

Create the application files in your repository:

- `docker/api/src/main.py` - Main FastAPI application
- `docker/api/src/logger.py` - Structured JSON logging setup

### Application Dependencies

Create `docker/api/requirements.txt`:

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.3
asyncpg==0.30.0
pydantic==2.11.0
ruff==0.11.0
python-json-logger==3.3.0
```

### Setup Development Environment

Create a virtual environment for IDE support and local development:

```bash
# Create virtual environment in project root
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows

# Install dependencies for IDE linting
pip install -r docker/api/requirements.txt

# Add virtual environment to .gitignore
echo "venv/" >> .gitignore
```

**Note:** This virtual environment is only for development/IDE support. The actual application runs in Docker containers.

### Create Docker Image

Create `docker/api/Dockerfile`:

```dockerfile
FROM python:3.13-slim

# Create a non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ .

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Security Benefits:**

- **Principle of least privilege** - Application runs with minimal permissions
- **Attack surface reduction** - If compromised, attacker has limited access
- **Kubernetes compatibility** - Many clusters enforce non-root policies
- **Best practice compliance** - Follows container security standards

---

## Step 3B: Build and Deploy API

Now we'll build the Docker image and create Kubernetes manifests for the API deployment.

### Build the API Image

```bash
# Configure Docker to use minikube's registry
eval $(minikube docker-env)

# Build the API image
docker build -t task-api:latest docker/api/

# Verify the image was built
docker images | grep task-api
```

### Create API Kubernetes Manifests

Create `k8s/base/api/api-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: task-mgmt
  labels:
    app: api
    tier: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
        tier: api
    spec:
      containers:
      - name: api
        image: task-api:latest
        imagePullPolicy: Never  # Use local image
        env:
        - name: DB_HOST
          value: "postgres"
        - name: DB_PORT
          value: "5432"
        - name: DB_NAME
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: POSTGRES_DB
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: POSTGRES_USER
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: POSTGRES_PASSWORD
        ports:
        - containerPort: 8000
          name: http
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "64Mi"
            cpu: "100m"
          limits:
            memory: "128Mi"
            cpu: "200m"
```

Create `k8s/base/api/api-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: task-mgmt
  labels:
    app: api
    tier: api
spec:
  type: ClusterIP
  ports:
  - port: 8000
    targetPort: 8000
    name: http
  selector:
    app: api
```

### Deploy the API

```bash
# Deploy API manifests
kubectl apply -f k8s/base/api/

# Verify deployment
kubectl get pods -n task-mgmt
kubectl get services -n task-mgmt
```

**Expected output:**

- API pods: `api-xxx` should be Running (2 replicas)
- API service: `api` should have ClusterIP assigned
- Both postgres and api services should be ready

## Step 4: NodePort External Access

Now we need to create a NodePort service that exposes our API to external traffic. This service will route traffic from port 30080 on your local machine to the internal API service.

**What is NodePort?** NodePort is one of three ways to expose a Kubernetes service externally. It opens a specific port (30000-32767 range) on every node in your cluster. Traffic sent to this port gets forwarded to your service. In minikube, this means we can access our API at `localhost:30080`.

### Create NodePort Service

Create `k8s/base/external/nodeport-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-nodeport
  namespace: task-mgmt
  labels:
    app: api
    tier: external
spec:
  type: NodePort
  ports:
  - port: 8000        # Port on the service
    targetPort: 8000  # Port on the API pods
    nodePort: 30080   # External port (30000-32767 range)
    name: http
  selector:
    app: api          # Routes to pods with app=api label
```

### Deploy NodePort Service

```bash
# Deploy the NodePort service
kubectl apply -f k8s/base/external/nodeport-service.yaml

# Verify the service was created
kubectl get services -n task-mgmt
kubectl get endpoints -n task-mgmt
```

**Expected output:**

- Service `api-nodeport` should show `NodePort` type with port `30080:8000/TCP`
- Endpoints should show the IP addresses of your API pods

### Test External Access

The API is working correctly internally. The logs show successful health check responses from Kubernetes probes.

**Method 1: kubectl port-forward (Working ✅)**

```bash
# Forward local port 8080 to the API service
kubectl port-forward -n task-mgmt svc/api 8080:8000

# In a new terminal:
curl http://localhost:8080/health
# Response: {"status":"healthy","service":"task-api"}
```

**Method 2: NodePort with minikube tunnel (Limited with Docker driver)**

```bash
# In a separate terminal, start minikube tunnel (requires sudo password)
sudo minikube tunnel

# Expected: This should make NodePort services accessible on localhost
curl http://localhost:30080/health

# Result on macOS Docker driver: Connection failed ❌
# Note: This is a known limitation of the Docker driver on macOS
# The tunnel works better with LoadBalancer services than NodePort services
```

**Why NodePort + tunnel doesn't work with Docker driver on macOS:**

- Docker driver creates additional networking isolation
- minikube tunnel has limited support for NodePort with Docker driver
- This would work with VM drivers (hyperkit, virtualbox) or in real clusters

**Service verification:**

```bash
# Check service endpoints
kubectl get endpoints api-nodeport -n task-mgmt
# Result: ✅ 10.244.0.8:8000,10.244.0.9:8000 (both API pods connected)

# Check service list
minikube service list
# Note: api-nodeport shows empty URL - this is a display issue with Docker driver
# The service itself works correctly (proven by option 3 success)
```

**Method 3: Use minikube service (Working ✅)**

```bash
# This automatically creates a tunnel and opens the service
minikube service api-nodeport -n task-mgmt

# Output shows both the original NodePort URL and the tunneled URL:
# |-----------|--------------|-------------|---------------------------|
# | NAMESPACE |     NAME     | TARGET PORT |            URL            |
# |-----------|--------------|-------------|---------------------------|
# | task-mgmt | api-nodeport | http/8000   | http://192.168.49.2:30080 |
# |-----------|--------------|-------------|---------------------------|
# 🏃  Starting tunnel for service api-nodeport.
# |-----------|--------------|-------------|------------------------|
# | NAMESPACE |     NAME     | TARGET PORT |          URL           |
# |-----------|--------------|-------------|------------------------|
# | task-mgmt | api-nodeport |             | http://127.0.0.1:65179 |
# |-----------|--------------|-------------|------------------------|

# The tunneled URL (127.0.0.1:65179) works in browser and with curl
```

**Method 4: Get URL without opening browser**

```bash
# Get the service URL without auto-opening browser
minikube service api-nodeport -n task-mgmt --url

# Use the returned URL for API calls
```

**Summary of access methods:**

|Method|Status|Use Case|
|---|---|---|
|`kubectl port-forward`|✅ Working|Development, debugging|
|`minikube service`|✅ Working|Automatic tunnel, browser testing|
|`minikube tunnel + NodePort`|❌ Limited|Docker driver limitation on macOS|
|Direct NodePort|❌ Not accessible|Requires real cluster or VM driver|

**Key learning:** The NodePort service is configured correctly and works perfectly. The networking limitations are specific to the local Docker environment, not your Kubernetes configuration.


**Why these differences exist:**

- **Real Kubernetes clusters**: NodePort works directly on node IPs
- **minikube with VM drivers**: NodePort works on minikube IP
- **minikube with Docker driver on macOS**: Requires tunnel due to Docker networking isolation
- **Port-forwarding**: Always works, commonly used for development

For production learning, `minikube tunnel` gives you the most realistic NodePort behavior. For daily development, port-forwarding is simpler.

## Step 5: End-to-End Verification

Now let's verify the complete task management functionality using our working connection.

### Test Health Endpoint

```bash
# Test the health endpoint first
curl http://localhost:8080/health
```

### Test Task Creation

```bash
curl -X POST http://localhost:8080/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "title": "My first task",
    "description": "Testing the task management system"
  }'

# Response: ✅
# {"id":1,"title":"My first task","description":"Testing the task management system","status":"pending","user_id":"test-user"}
```

### Test Task Listing

```bash
# List tasks for the user
curl http://localhost:8080/tasks?user_id=test-user

# Expected response:
# [{"id": 1, "title": "My first task", ...}]
```

### Test Task Listing 

```bash
curl http://localhost:8080/tasks?user_id=test-user

# Response: ✅
# [{"id":1,"title":"My first task","description":"Testing the task management system","status":"pending","user_id":"test-user"}]
```

### Verify Database Persistence 

```bash
# Create another task
curl -X POST http://localhost:8080/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user", 
    "title": "Second task",
    "description": "Testing data persistence"
  }'

# List all tasks to verify both are stored
curl http://localhost:8080/tasks?user_id=test-user

# Response: ✅
# [{"id":2,"title":"Second task","description":"Testing data persistence","status":"pending","user_id":"test-user"},{"id":1,"title":"My first task","description":"Testing the task management system","status":"pending","user_id":"test-user"}]
```

## Phase 1 Complete! 

**What we accomplished:**

- ✅ Deployed PostgreSQL with persistent storage
- ✅ Created and deployed FastAPI service with 2 replicas
- ✅ Established external access via NodePort (with port-forwarding)
- ✅ Verified end-to-end task creation and listing functionality
- ✅ Confirmed database persistence across multiple requests

**Key Kubernetes concepts learned:**

- **Persistent Volumes and Claims**: Database data survives pod restarts
- **Secrets management**: Database credentials stored securely
- **Service types**: ClusterIP for internal communication, NodePort for external access
- **Pod-to-pod communication**: API pods connecting to PostgreSQL via service DNS
- **Health checks**: Liveness and readiness probes ensuring pod health
- **Resource management**: CPU and memory limits on all containers

**Current architecture:**

```
External (localhost:8080) → kubectl port-forward → API Service → API Pods (2) → PostgreSQL Service → PostgreSQL Pod
                                                                              ↓
                                                                    Persistent Volume (5GB)
```

**Next steps for Phase 2:**

- Deploy worker pods for asynchronous task processing
- Add load generator pods for traffic simulation
- Implement horizontal pod autoscaling (HPA)
- Test system behavior under load

**Cleanup commands (if needed):**

```bash
# Remove all Phase 1 resources
kubectl delete namespace task-mgmt

# Stop port-forwarding
# Press Ctrl+C in the port-forward terminal
```

