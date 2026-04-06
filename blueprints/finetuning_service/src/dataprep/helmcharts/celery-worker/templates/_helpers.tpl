{{- define "celery.name" -}}
celery
{{- end -}}

{{- define "celery.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "celery.name" .) -}}
{{- end -}}

{{- define "celery.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version -}}
{{- end -}}
