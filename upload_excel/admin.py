from django.contrib import admin
from.models import UploadedFile, AMC , MutualFundScheme
# Register your models here.

class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('scheme', 'file', 'uploaded_at')
admin.site.register(UploadedFile, UploadedFileAdmin)

class AMCAdmin(admin.ModelAdmin):
    list_display = ('name',)
admin.site.register(AMC, AMCAdmin)

class MutualFundSchemeAdmin(admin.ModelAdmin):
    list_display = ('amc', 'scheme_name')
admin.site.register(MutualFundScheme, MutualFundSchemeAdmin)