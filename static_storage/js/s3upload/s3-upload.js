overwrite = false;

var overwriteS3Upload = function (file) {
  $("input[name=upload-overwrite]:radio").change(function () {
    if ($(this).val() === "yes") {
      overwrite = true;
      getSignedRequest(file);
      $(".overwrite").removeClass("overwrite-active");
      $("#help1div").hide();
    }
  });
};

// Obtains a pre-signed request from the server for the selected file
function getSignedRequest (file) {
  var xhr = new XMLHttpRequest();
  if (overwrite === true) {
    xhr.open("GET", "/sign_s3?file_name=" + file.name + "&file_type=" + file.type + "&file_size=" + file.size + "&overwrite=true");
  } else {
    xhr.open("GET", "/sign_s3?file_name=" + file.name + "&file_type=" + file.type + "&file_size=" + file.size + "&overwrite=false");
  }
  xhr.onreadystatechange = function () {
    if (xhr.readyState === 4) {
      if (xhr.status === 200) {
        var response = $.parseJSON(xhr.responseText);
        overwrite_file = file;
        if (response.data != "exists" || overwrite === true) {
          uploadFile(file, response.data);
        } else {
          $("#SwatModel").val("");
          $(".overwrite").addClass("overwrite-active");
          $("#help1div").append('File already exists on S3. Choose to overwrite or click Validate to continue.');
          $("#help1div").show();
          overwriteS3Upload(file);
        }
      } else {
        alert("Could not get signed URL.");
      }
    }
  };
  xhr.send();
}

// Uses pre-signed request to upload file to S3
function uploadFile (file, s3Data) {
  var xhr = new XMLHttpRequest();
  xhr.open("POST", s3Data.url);

  $(".progress").addClass("progress-active");

  var postData = new FormData();
  for (key in s3Data.fields) {
    postData.append(key, s3Data.fields[key]);
  }
  postData.append("file", file);

  xhr.upload.onprogress = function(data) {
    progressBar(data, true);
  };

  xhr.onreadystatechange = function () {
    if (xhr.readyState === 4) {
      if (xhr.status === 200 || xhr.status === 204) {
        // do something with the s3 file url
        setTimeout(function () {
          $(".progress").removeClass("progress-active");
          var bar = document.querySelector(".bar");
          bar.style.width = "0%";
        }, 2000);
        setTimeout(function () {
          successfulUpload($("#SwatModel"), file.name);
        }, 2500);
      } else {
        alert("Could not upload file.");
      }
    }
  };
  xhr.send(postData);
}

var progressBar = function(data, showProgress) {
  if (data.lengthComputable === false || showProgress === false) return;

  var pcnt = Math.round(data.loaded * 100 / data.total),
      bar = document.querySelector(".bar");

  bar.style.width = pcnt + "%"
};

var successfulUpload = function(el, fileName) {
  el.val("");
  $("#uploadAlert").append('Successfully uploaded "' + fileName + '". Click Validate to continue.');
  $("#uploadAlert").show();
  setTimeout(function () {
    $("#uploadAlert").hide();
  }, 7000);
};