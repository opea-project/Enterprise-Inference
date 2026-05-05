{{- define "redis.name" -}}
redis
{{- end -}}

{{- define "redis.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "redis.name" .) -}}
{{- end -}}

{{- define "redis.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version -}}
{{- end -}}
