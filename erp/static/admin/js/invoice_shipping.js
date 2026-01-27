document.addEventListener("DOMContentLoaded", function () {
    var checkbox = document.getElementById('same_as_bill_to');

    // The rows we want to hide/show
    var shipRows = [
        document.querySelector('.field-shipping_name'),
        document.querySelector('.field-shipping_address'),
        document.querySelector('.field-shipping_state'),
        document.querySelector('.field-shipping_gstin')
    ];

    function toggleShipping() {
        if (checkbox.checked) {
            // Hide fields if Checked
            shipRows.forEach(function (row) {
                if (row) row.style.display = 'none';
            });
        } else {
            // Show fields if Unchecked
            shipRows.forEach(function (row) {
                if (row) row.style.display = 'block';
            });
        }
    }

    if (checkbox) {
        checkbox.addEventListener('change', toggleShipping);
        // Run once when page loads to set initial state
        toggleShipping();
    }
});