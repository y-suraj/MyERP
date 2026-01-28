document.addEventListener("DOMContentLoaded", function () {
    var checkbox = document.getElementById('same_as_bill_to');

    // The Input Fields (We need to clear these when checked)
    var shipName = document.getElementById('id_shipping_name');
    var shipAddr = document.getElementById('id_shipping_address');
    var shipState = document.getElementById('id_shipping_state');
    var shipGst = document.getElementById('id_shipping_gstin');

    // The Rows (We need to hide these)
    var shipRows = [
        document.querySelector('.field-shipping_name'),
        document.querySelector('.field-shipping_address'),
        document.querySelector('.field-shipping_state'),
        document.querySelector('.field-shipping_gstin')
    ];

    function toggleShipping(e) {
        // If this was triggered by a user click (event exists), clear the data
        var isUserClick = e && e.type === 'change';

        if (checkbox.checked) {
            // 1. Hide Fields
            shipRows.forEach(function (row) { if (row) row.style.display = 'none'; });

            // 2. CRITICAL FIX: Clear data so it doesn't save to DB!
            if (isUserClick) {
                if (shipName) shipName.value = "";
                if (shipAddr) shipAddr.value = "";
                if (shipGst) shipGst.value = "";
                if (shipState) shipState.selectedIndex = 0; // Reset dropdown
            }
        } else {
            // Show Fields
            shipRows.forEach(function (row) { if (row) row.style.display = 'block'; });
        }
    }

    if (checkbox && shipName) {
        // INITIAL LOAD LOGIC:
        // If the name field is empty, we assume "Same as Bill To" is active.
        if (shipName.value.trim() === "") {
            checkbox.checked = true;
            // Manually hide rows (don't call toggleShipping to avoid clearing potential data on load)
            shipRows.forEach(function (row) { if (row) row.style.display = 'none'; });
        } else {
            checkbox.checked = false;
            shipRows.forEach(function (row) { if (row) row.style.display = 'block'; });
        }

        // Listen for clicks
        checkbox.addEventListener('change', toggleShipping);
    }
});