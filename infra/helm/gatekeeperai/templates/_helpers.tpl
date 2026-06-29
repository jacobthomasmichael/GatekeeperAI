{{/*
Expand the name of the chart.
*/}}
{{- define "gatekeeperai.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
Truncated at 63 chars because Kubernetes name fields are limited to this length.
*/}}
{{- define "gatekeeperai.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label — used in selector labels.
*/}}
{{- define "gatekeeperai.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "gatekeeperai.labels" -}}
helm.sh/chart: {{ include "gatekeeperai.chart" . }}
{{ include "gatekeeperai.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels — used in Deployment selectors and Service selectors.
These must not change after initial deploy without a full rollout.
*/}}
{{- define "gatekeeperai.selectorLabels" -}}
app.kubernetes.io/name: {{ include "gatekeeperai.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Image reference helper — combines registry, image name, and tag.
Usage: {{ include "gatekeeperai.image" (dict "registry" .Values.image.registry "name" "gatekeeperai/backend" "tag" .Values.image.tag) }}
*/}}
{{- define "gatekeeperai.image" -}}
{{- if .registry }}
{{- printf "%s/%s:%s" .registry .name .tag }}
{{- else }}
{{- printf "%s:%s" .name .tag }}
{{- end }}
{{- end }}

{{/*
Common environment variables injected into every backend container
(api, worker, beat). Keeps the individual deployment templates DRY.
*/}}
{{- define "gatekeeperai.backendEnv" -}}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "gatekeeperai.fullname" . }}-secrets
      key: database-url
- name: REDIS_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "gatekeeperai.fullname" . }}-secrets
      key: redis-url
- name: SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "gatekeeperai.fullname" . }}-secrets
      key: secret-key
- name: SECRET_ENCRYPTION_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "gatekeeperai.fullname" . }}-secrets
      key: secret-encryption-key
- name: ANTHROPIC_API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "gatekeeperai.fullname" . }}-secrets
      key: anthropic-api-key
- name: GIT_REPOS_BASE_PATH
  value: /git-repos
- name: ENVIRONMENT
  value: {{ .Values.env.environment | quote }}
- name: APP_BASE_URL
  value: {{ .Values.env.appBaseUrl | quote }}
- name: HOOK_CALLBACK_URL
  value: {{ .Values.env.hookCallbackUrl | quote }}
- name: GIT_SSH_HOST
  value: {{ .Values.env.gitSshHost | quote }}
- name: GIT_SSH_PORT
  value: {{ .Values.env.gitSshPort | quote }}
- name: HOOK_SECRET
  value: {{ .Values.env.hookSecret | quote }}
- name: DEPLOY_BACKEND
  value: {{ .Values.env.deployBackend | quote }}
- name: AWS_REGION
  value: {{ .Values.aws.region | quote }}
- name: BUILD_CONTEXT_BUCKET
  value: {{ .Values.aws.buildContextBucket | quote }}
- name: ECR_REGISTRY
  value: {{ .Values.aws.ecrRegistry | quote }}
- name: K8S_APPS_NAMESPACE
  value: {{ .Values.namespaces.apps | quote }}
- name: K8S_BUILDS_NAMESPACE
  value: {{ .Values.namespaces.builds | quote }}
- name: K8S_WORKER_SA_NAME
  value: {{ include "gatekeeperai.fullname" . }}-worker
- name: KANIKO_IMAGE
  value: {{ .Values.kaniko.image | quote }}
{{- end }}
