SERVICE="mysql"
HELM_DIR="bitnami/mysql"
NAMESPACE="database"
DOCKER_REGISTRY="bitnamilegacy"  
TAG="8.0.34-debian-11-r31"

# helm uninstall mysql -n database
# kubectl delete pvc -l app.kubernetes.io/instance=mysql -n database

helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm upgrade --force --install ${SERVICE} ${HELM_DIR} \
  --values ${SERVICE}/values.yaml \
  --namespace ${NAMESPACE} \
  --create-namespace \
  --set image.repository=${DOCKER_REGISTRY}/${SERVICE} \
  --set image.tag=${TAG}
