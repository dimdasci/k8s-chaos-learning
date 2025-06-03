.PHONY: fmt lint lint-check

# Python code formatting and linting
fmt:
	@echo "Formatting Python code..."
	cd docker/api && ruff format src/

lint:
	@echo "Linting and fixing Python code..."
	cd docker/api && ruff check --fix src/

lint-check:
	@echo "Checking Python code (no fixes)..."
	cd docker/api && ruff check src/


# Phase 1: Basic deployment commands

.PHONY: help build-api deploy-database deploy-api deploy-nodeport deploy-phase1 clean-phase1 restart-api logs status test-health test-tasks

# Default target
help:
	@echo "Available commands:"
	@echo "  setup-env      - Configure minikube Docker environment"
	@echo "  build-api      - Build API Docker image"
	@echo "  deploy-phase1  - Deploy complete Phase 1 system"
	@echo "  deploy-database- Deploy PostgreSQL database only"
	@echo "  deploy-api     - Deploy API service only"
	@echo "  deploy-nodeport- Deploy NodePort service only"
	@echo "  restart-api    - Restart API deployment"
	@echo "  clean-phase1   - Remove all Phase 1 resources"
	@echo "  logs           - Show application logs"
	@echo "  status         - Show deployment status"
	@echo "  test-health    - Test API health endpoint"
	@echo "  test-tasks     - Test task creation and listing"
	@echo "  port-forward   - Start port forwarding to API"
	@echo "  tunnel         - Start minikube service tunnel"

# Environment setup
setup-env:
	@echo "Configuring minikube Docker environment..."
	eval $$(minikube docker-env)
	@echo "Environment configured. Run in your terminal:"
	@echo "eval \$$(minikube docker-env)"

# Build images
build-api:
	@echo "Building API Docker image..."
	eval $$(minikube docker-env) && docker build -t task-api:latest docker/api/
	@echo "Verifying image was built..."
	eval $$(minikube docker-env) && docker images | grep task-api

# Database deployment
deploy-database:
	@echo "Deploying PostgreSQL database..."
	kubectl apply -f k8s/base/namespace.yaml
	kubectl apply -f k8s/base/database/postgres-secret.yaml
	kubectl apply -f k8s/base/database/postgres-pv.yaml
	kubectl apply -f k8s/base/database/postgres-pvc.yaml
	kubectl apply -f k8s/base/database/postgres-deployment.yaml
	kubectl apply -f k8s/base/database/postgres-service.yaml
	@echo "Waiting for database to be ready..."
	kubectl wait --for=condition=ready pod -l app=postgres -n task-mgmt --timeout=120s

# API deployment
deploy-api:
	@echo "Deploying API service..."
	kubectl apply -f k8s/base/api/api-deployment.yaml
	kubectl apply -f k8s/base/api/api-service.yaml
	@echo "Waiting for API deployment to be ready..."
	kubectl wait --for=condition=ready pod -l app=api -n task-mgmt --timeout=120s

# NodePort deployment
deploy-nodeport:
	@echo "Deploying NodePort service..."
	kubectl apply -f k8s/base/external/nodeport-service.yaml

# Complete Phase 1 deployment
deploy-phase1: deploy-database deploy-api deploy-nodeport
	@echo "Phase 1 deployment complete!"
	@echo ""
	@echo "Available access methods:"
	@echo "1. Port forwarding: make port-forward"
	@echo "2. Service tunnel:  make tunnel" 
	@echo "3. Test endpoints:  make test-health"

# Restart API
restart-api:
	@echo "Restarting API deployment..."
	kubectl rollout restart deployment/api -n task-mgmt
	kubectl rollout status deployment/api -n task-mgmt

# Access methods
port-forward:
	@echo "Starting port forwarding to API service..."
	@echo "API will be available at http://localhost:8080"
	@echo "Press Ctrl+C to stop"
	kubectl port-forward -n task-mgmt svc/api 8080:8000

tunnel:
	@echo "Starting minikube service tunnel..."
	@echo "This will open the API in your browser"
	minikube service api-nodeport -n task-mgmt

# Monitoring and debugging
logs:
	@echo "Showing API logs..."
	kubectl logs -n task-mgmt -l app=api --tail=50 -f

status:
	@echo "=== Namespace ==="
	kubectl get namespaces | grep task-mgmt
	@echo ""
	@echo "=== Pods ==="
	kubectl get pods -n task-mgmt
	@echo ""
	@echo "=== Services ==="
	kubectl get services -n task-mgmt
	@echo ""
	@echo "=== Endpoints ==="
	kubectl get endpointslices -n task-mgmt
	@echo ""
	@echo "=== Persistent Volumes ==="
	kubectl get pv,pvc -n task-mgmt

# Testing
test-health:
	@echo "Testing API health endpoint..."
	@echo "Note: Requires port-forward to be running in another terminal"
	@echo "Run 'make port-forward' first if not already running"
	curl -f http://localhost:8080/health || echo "Failed - ensure port-forward is running"

test-tasks:
	@echo "Testing task creation and listing..."
	@echo "Creating a test task..."
	curl -X POST http://localhost:8080/tasks \
		-H "Content-Type: application/json" \
		-d '{"user_id": "makefile-test", "title": "Test task from Makefile", "description": "Testing automation"}'
	@echo ""
	@echo "Listing tasks for test user..."
	curl http://localhost:8080/tasks?user_id=makefile-test

# Cleanup
clean-phase1:
	@echo "Removing Phase 1 deployment..."
	kubectl delete namespace task-mgmt --ignore-not-found=true
	@echo "Phase 1 resources removed"

# Shortcuts for common workflows
quick-deploy: setup-env build-api deploy-phase1
	@echo "Quick deployment complete!"

quick-test: test-health test-tasks
	@echo "Testing complete!"

rebuild-api: build-api restart-api
	@echo "API rebuilt and restarted!"