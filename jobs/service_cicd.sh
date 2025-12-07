

# Load values.yaml into environment variables
source ../values/values.properties

echo "Logging into Docker registry: ${DOCKER_REGISTRY}"

SERVICE="$1"
TAG="$2"
NAMESPACE="$3"

SERVICE_DIR="../service/$SERVICE/"
HELM_DIR="../helm/$SERVICE/"
VALUES_DIR="../values/$SERVICE/"

# docker login
docker login -u ${DOCKER_USERNAME} -p ${DOCKER_PASSWORD}

# # go the service directory
docker build -t ${DOCKER_REGISTRY}/${SERVICE}:${TAG} ${SERVICE_DIR}/

# # push the docker image to docker hub
docker push ${DOCKER_REGISTRY}/${SERVICE}:${TAG}

# # helm install
helm upgrade --force --install ${SERVICE} ${HELM_DIR} --values ${VALUES_DIR}/values.yaml --namespace ${NAMESPACE} --create-namespace  --set image.repository=${DOCKER_REGISTRY}/${SERVICE} --set image.tag=${TAG}
kubectl rollout restart deployment/${SERVICE} -n ${NAMESPACE}

