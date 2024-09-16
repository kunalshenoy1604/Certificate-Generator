// JS for dynamically placing text fields in the admin side (optional, for customizing template)

window.onload = function () {
    var canvas = document.getElementById('templateCanvas');
    var ctx = canvas.getContext('2d');
    var img = new Image();
    img.src = '/path/to/uploaded/template';  // Uploaded template image path

    img.onload = function () {
        ctx.drawImage(img, 0, 0);
    };

    canvas.addEventListener('click', function (event) {
        var x = event.offsetX;
        var y = event.offsetY;
        // Let admin choose where to place the text
        ctx.fillText("Name", x, y); // placeholder for name
    });
};
