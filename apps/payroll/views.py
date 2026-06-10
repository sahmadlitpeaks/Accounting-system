from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Employee, PayrollRun, Payslip
from .services import PayrollError, pay_salaries, run_payroll


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = "__all__"


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.name", read_only=True)

    class Meta:
        model = Payslip
        fields = "__all__"


class PayrollRunSerializer(serializers.ModelSerializer):
    payslips = PayslipSerializer(many=True, read_only=True)

    class Meta:
        model = PayrollRun
        fields = "__all__"


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    filterset_fields = ["company", "is_active"]


class PayrollRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PayrollRun.objects.prefetch_related("payslips").all()
    serializer_class = PayrollRunSerializer
    filterset_fields = ["company", "status"]

    @action(detail=False, methods=["post"])
    def run(self, request):
        from datetime import date as _date

        from apps.core.models import Company

        company = Company.objects.get(pk=request.data["company"])
        try:
            run = run_payroll(company, request.data.get("date") or _date.today())
        except PayrollError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(PayrollRunSerializer(run).data, status=201)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        from datetime import date as _date

        try:
            run = pay_salaries(self.get_object(), request.data.get("date") or _date.today())
        except PayrollError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(PayrollRunSerializer(run).data)
