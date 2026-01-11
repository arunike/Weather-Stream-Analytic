#!/bin/bash

# 1. Check Prerequisites
if ! command -v helm &> /dev/null; then
    echo "❌ Helm is not installed. Please install it first."
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed."
    exit 1
fi

# 2. Build Dependencies
echo "📦 Building Helm dependencies..."
helm dependency build ./k8s/fraud-detection-platform

# 3. Install/Upgrade Chart
echo "🚀 Deploying to Kubernetes..."
# We use 'fraud-stack' as the release name
helm upgrade --install fraud-stack ./k8s/fraud-detection-platform \
    --set generator.image.pullPolicy=Never \
    --set detector.image.pullPolicy=Never \
    --set dashboard.image.pullPolicy=Never \
    --set spark.master.image=apache/spark:3.5.0 \
    --set spark.worker.image=apache/spark:3.5.0

# 4. Wait for Pods
echo "⏳ Waiting for pods to verify deployment..."
kubectl rollout status deployment/fraud-stack-dashboard
kubectl rollout status deployment/fraud-stack-spark-master
kubectl rollout status deployment/fraud-stack-generator

echo "✅ Deployment Successful!"
echo ""
echo "🔍 Verify the dashboard:"
echo "   kubectl port-forward svc/fraud-stack-dashboard 8501:8501"
echo "   Then open http://localhost:8501"
