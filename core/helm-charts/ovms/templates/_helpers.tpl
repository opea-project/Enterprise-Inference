# Copyright (C) 2024-2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

{{/*
Expand the name of the chart.
*/}}
{{- define "ovms-model-server.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ovms-model-server.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "ovms-model-server.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ovms-model-server.labels" -}}
helm.sh/chart: {{ include "ovms-model-server.chart" . }}
{{ include "ovms-model-server.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ovms-model-server.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ovms-model-server.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- with .Values.podLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ovms-model-server.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ovms-model-server.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Generate list of enabled models
*/}}
{{- define "ovms-model-server.enabledModels" -}}
{{- $models := list }}
{{- range .Values.models }}
{{- if .enabled }}
{{- $models = append $models . }}
{{- end }}
{{- end }}
{{- $models | toJson }}
{{- end }}

{{/*
Get the first enabled model (for single model deployment)
*/}}
{{- define "ovms-model-server.firstEnabledModel" -}}
{{- range .Values.models }}
{{- if .enabled }}
{{- . | toJson }}
{{- break }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Generate storage volume configuration
*/}}
{{- define "ovms-model-server.storageVolume" -}}
{{- if .Values.storage.persistentVolume.enabled }}
persistentVolumeClaim:
  claimName: {{ .Values.storage.persistentVolume.existingClaim | default (include "ovms-model-server.fullname" .) }}
{{- else }}
emptyDir:
  {{- if .Values.storage.emptyDir.sizeLimit }}
  sizeLimit: {{ .Values.storage.emptyDir.sizeLimit }}
  {{- end }}
{{- end }}
{{- end }}

{{/*
Generate OIDC secret name
*/}}
{{- define "ovms-model-server.oidcSecretName" -}}
{{- printf "%s-oidc" (include "ovms-model-server.fullname" .) }}
{{- end }}

{{/*
Generate image pull secrets
*/}}
{{- define "ovms-model-server.imagePullSecrets" -}}
{{- if .Values.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}
