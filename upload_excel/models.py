from django.db import models

class AMC(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class MutualFundScheme(models.Model):
    amc = models.ForeignKey(AMC, on_delete=models.CASCADE, related_name="schemes")
    scheme_name = models.CharField(max_length=255)

    def __str__(self):
        return self.scheme_name

class UploadedFile(models.Model):
    amc = models.ForeignKey(AMC, on_delete=models.CASCADE)
    scheme = models.ForeignKey(MutualFundScheme, on_delete=models.CASCADE , null= True)
    file = models.FileField(upload_to="uploads/")
    uploaded_at = models.DateTimeField(auto_now_add=True)



    def __str__(self):
        return f"{self.file.name} - {self.uploaded_at}"
