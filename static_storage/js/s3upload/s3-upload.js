// Obtains a pre-signed request from the server for the selected file
function getSignedRequest (file) {
  var xhr = new XMLHttpRequest();
  xhr.open("GET", "/sign_s3?file_name=" + file.name + "&file_type=" + file.type);
  xhr.onreadystatechange = function () {
    if (xhr.readyState === 4) {
      if (xhr.status === 200) {
        var response = $.parseJSON(xhr.responseText);
        uploadFile(file, response.data, response.url);
      } else {
        alert("Could not get signed URL.");
      }
    }
  };
  xhr.send();
}

// Uses pre-signed request to upload file to S3
function uploadFile (file, s3Data, url) {
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
          bar.style.width = "0%"
        }, 2000);
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