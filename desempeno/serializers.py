from rest_framework import serializers

class KPISerializer(serializers.Serializer):
    scope = serializers.CharField()
    scope_id = serializers.IntegerField(allow_null=True)
    desde = serializers.DateField(allow_null=True)
    hasta = serializers.DateField(allow_null=True)

    citas_total = serializers.IntegerField()
    citas_programadas = serializers.IntegerField()
    citas_completadas = serializers.IntegerField()
    citas_canceladas = serializers.IntegerField()

    tasa_cumplimiento = serializers.FloatField()
    tasa_cancelacion = serializers.FloatField()

    duracion_promedio_min = serializers.FloatField(allow_null=True)
    lead_time_promedio_h = serializers.FloatField(allow_null=True)

class SeriePuntoSerializer(serializers.Serializer):
    x = serializers.CharField()
    y = serializers.FloatField()

class SerieSerializer(serializers.Serializer):
    metric = serializers.CharField()
    group_by = serializers.CharField()
    points = SeriePuntoSerializer(many=True)

class RankingItemSerializer(serializers.Serializer):
    entity_id = serializers.IntegerField()
    entity_name = serializers.CharField()
    value = serializers.FloatField()

class RankingSerializer(serializers.Serializer):
    by = serializers.CharField()
    items = RankingItemSerializer(many=True)
