# Copyright (C) 2025-2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

{{- define "sglang.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "sglang.fullname" -}}
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

{{- define "sglang.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "sglang.labels" -}}
helm.sh/chart: {{ include "sglang.chart" . }}
{{ include "sglang.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "sglang.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sglang.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- with .Values.podLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{- define "sglang.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "sglang.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "sglang.storageVolume" -}}
{{- if .Values.storage.persistentVolume.enabled }}
persistentVolumeClaim:
  claimName: {{ .Values.storage.persistentVolume.existingClaim | default (include "sglang.fullname" .) }}
{{- else if .Values.storage.emptyDir.enabled }}
emptyDir:
  {{- if .Values.storage.emptyDir.sizeLimit }}
  sizeLimit: {{ .Values.storage.emptyDir.sizeLimit }}
  {{- end }}
{{- else }}
emptyDir: {}
{{- end }}
{{- end }}

{{- define "sglang.oidcSecretName" -}}
{{- printf "%s-oidc" (include "sglang.fullname" .) }}
{{- end }}

{{- define "sglang.imagePullSecrets" -}}
{{- if .Values.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}
