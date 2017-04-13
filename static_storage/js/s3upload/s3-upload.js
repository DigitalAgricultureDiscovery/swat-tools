// Obtains a pre-signed request from the server for the selected file
function getSignedRequest (file) {
  var xhr = new XMLHttpRequest();
  xhr.open("GET", "/sign_s3?file_name=" + file.name + "&file_type=" + file.type + "&file_size=" + file.size);
  xhr.onreadystatechange = function () {
    if (xhr.readyState === 4) {
      if (xhr.status === 200) {
        var response = $.parseJSON(xhr.responseText);
        if (response.data != "exists") {
          uploadFile(file, response.data);
        } else{
          alert("File already exists.");
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