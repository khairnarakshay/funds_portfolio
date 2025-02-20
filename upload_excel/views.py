# from django.shortcuts import render, redirect
from django.http import HttpResponse
# from django.core.files.storage import FileSystemStorage
# from .models import UploadedFile, AMC
# import pandas as pd
# from datetime import datetime

# def upload_file(request):
#     amcs = AMC.objects.all()  # Fetch AMC names from DB

#     if request.method == 'POST' and request.FILES.get('file'):
#         uploaded_file = request.FILES['file']
#         amc_id = request.POST['dropdown']
#         amc_name = AMC.objects.get(id=amc_id)  # Get AMC object

#         # Save the file and details in DB
#         UploadedFile.objects.create(
#             file=uploaded_file,
#             amc_name=amc_name.name,  # Store AMC name
#             upload_date=datetime.now()
#         )

#         return redirect('success_page')

#     return render(request, 'upload.html', {'amcs': amcs})




from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import AMC, MutualFundScheme, UploadedFile
from .forms import UploadFileForm

def upload_file_view(request):
    amcs = AMC.objects.all()
    
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            #form fields
            

            form.save()
            return redirect("success_page")  # Redirect to a success page

    else:
        form = UploadFileForm()
    
    return render(request, "upload.html", {"form": form, "amcs": amcs})

def get_schemes(request, amc_id):
    schemes = MutualFundScheme.objects.filter(amc_id=amc_id).values("id", "scheme_name")
    return JsonResponse({"schemes": list(schemes)})
    print(schemes)


def success_page(request):
     return HttpResponse('File uploaded successfully!')

