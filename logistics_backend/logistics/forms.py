from django import forms


class ReferenceForm(forms.Form):
    reference = forms.CharField(label='Наименование', required=True, max_length=100)


class EmployeesForm(forms.Form):
    last_name = forms.CharField(label='Фамилия сотрудника', required=True, max_length=100)
    first_name = forms.CharField(label='Имя сотрудника', required=True, max_length=100)
    middle_name = forms.CharField(label='Отчество сотрудника', required=False, max_length=100)
    organization = forms.CharField(label='Организация', required=False, max_length=100)

