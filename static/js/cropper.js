let cropper = null;

// Wrapper that adds an onSaved callback, used by crop.html
function initializeCropperWithCallback(imageUrl, workbookIndex, onSaved) {
    initializeCropper(imageUrl, workbookIndex, onSaved);
}

function initializeCropper(imageUrl, workbookIndex, onSaved) {
    const canvas = document.getElementById('cropCanvas');
    const ctx = canvas.getContext('2d');
    const container = document.getElementById('cropContainer');
    const resetBtn = document.getElementById('resetSelection');
    const saveBtn = document.getElementById('saveCrop');
    const cropInfo = document.getElementById('cropInfo');
    const cropDimensions = document.getElementById('cropDimensions');
    
    let img = new Image();
    let isDrawing = false;
    let startX, startY, endX, endY;
    let selection = null;
    
    img.onload = function() {
        // Set canvas size to image size
        canvas.width = img.width;
        canvas.height = img.height;
        
        // Draw the image
        ctx.drawImage(img, 0, 0);
        
        // Set canvas display size for responsive behavior
        const maxWidth = container.offsetWidth - 40; // Account for padding
        if (img.width > maxWidth) {
            const scale = maxWidth / img.width;
            canvas.style.width = maxWidth + 'px';
            canvas.style.height = (img.height * scale) + 'px';
        }
    };
    
    img.onerror = function() {
        alert('Failed to load image for cropping');
    };
    
    img.src = imageUrl;
    
    // Mouse event handlers
    canvas.addEventListener('mousedown', function(e) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        
        startX = (e.clientX - rect.left) * scaleX;
        startY = (e.clientY - rect.top) * scaleY;
        isDrawing = true;
        
        // Clear previous selection
        selection = null;
        redrawCanvas();
    });
    
    canvas.addEventListener('mousemove', function(e) {
        if (!isDrawing) return;
        
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        
        endX = (e.clientX - rect.left) * scaleX;
        endY = (e.clientY - rect.top) * scaleY;
        
        // Redraw canvas with selection rectangle
        redrawCanvas();
        drawSelection();
        updateCropInfo();
    });
    
    canvas.addEventListener('mouseup', function(e) {
        if (!isDrawing) return;
        
        isDrawing = false;
        
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        
        endX = (e.clientX - rect.left) * scaleX;
        endY = (e.clientY - rect.top) * scaleY;
        
        // Create selection object
        const x = Math.min(startX, endX);
        const y = Math.min(startY, endY);
        const width = Math.abs(endX - startX);
        const height = Math.abs(endY - startY);
        
        if (width > 10 && height > 10) { // Minimum selection size
            selection = { x, y, width, height };
            resetBtn.disabled = false;
            saveBtn.disabled = false;
            redrawCanvas();
            drawSelection();
            updateCropInfo();
        } else {
            selection = null;
            resetBtn.disabled = true;
            saveBtn.disabled = true;
            cropInfo.style.display = 'none';
        }
    });
    
    // Touch events for mobile support
    canvas.addEventListener('touchstart', function(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousedown', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        canvas.dispatchEvent(mouseEvent);
    });
    
    canvas.addEventListener('touchmove', function(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousemove', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        canvas.dispatchEvent(mouseEvent);
    });
    
    canvas.addEventListener('touchend', function(e) {
        e.preventDefault();
        const mouseEvent = new MouseEvent('mouseup', {});
        canvas.dispatchEvent(mouseEvent);
    });
    
    function redrawCanvas() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
    }
    
    function drawSelection() {
        if (!selection && isDrawing) {
            // Draw current selection being made
            const x = Math.min(startX, endX);
            const y = Math.min(startY, endY);
            const width = Math.abs(endX - startX);
            const height = Math.abs(endY - startY);
            
            ctx.strokeStyle = '#dc3545';
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]);
            ctx.strokeRect(x, y, width, height);
            
            // Add semi-transparent overlay
            ctx.fillStyle = 'rgba(220, 53, 69, 0.1)';
            ctx.fillRect(x, y, width, height);
        } else if (selection) {
            // Draw final selection
            ctx.strokeStyle = '#dc3545';
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]);
            ctx.strokeRect(selection.x, selection.y, selection.width, selection.height);
            
            // Add semi-transparent overlay
            ctx.fillStyle = 'rgba(220, 53, 69, 0.1)';
            ctx.fillRect(selection.x, selection.y, selection.width, selection.height);
        }
        
        ctx.setLineDash([]); // Reset line dash
    }
    
    function updateCropInfo() {
        if (selection || (isDrawing && Math.abs(endX - startX) > 10 && Math.abs(endY - startY) > 10)) {
            const x = selection ? selection.x : Math.min(startX, endX);
            const y = selection ? selection.y : Math.min(startY, endY);
            const width = selection ? selection.width : Math.abs(endX - startX);
            const height = selection ? selection.height : Math.abs(endY - startY);
            
            cropDimensions.textContent = `${Math.round(width)} × ${Math.round(height)} pixels at (${Math.round(x)}, ${Math.round(y)})`;
            cropInfo.style.display = 'block';
        } else {
            cropInfo.style.display = 'none';
        }
    }
    
    // Reset button handler
    resetBtn.addEventListener('click', function() {
        selection = null;
        isDrawing = false;
        resetBtn.disabled = true;
        saveBtn.disabled = true;
        cropInfo.style.display = 'none';
        redrawCanvas();
    });
    
    // Save button handler
    saveBtn.addEventListener('click', function() {
        if (!selection) return;
        
        saveBtn.disabled = true;
        const originalText = saveBtn.innerHTML;
        saveBtn.innerHTML = '<i data-feather="loader"></i> Saving...';
        feather.replace();
        
        fetch('/save_crop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                workbook_index: workbookIndex,
                crop_data: selection
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error saving crop: ' + data.error);
                return;
            }

            // Show success message
            saveBtn.innerHTML = '<i data-feather="check"></i> Saved!';
            saveBtn.classList.remove('btn-success');
            saveBtn.classList.add('btn-outline-success');
            feather.replace();

            // Pass thumbnail data back to parent window (index page)
            if (window.opener && data.thumbnail_filename) {
                window.opener.postMessage({
                    type: 'cropComplete',
                    workbookIndex: workbookIndex,
                    thumbnailFilename: data.thumbnail_filename
                }, '*');
            }

            // If a callback was supplied (crop.html zone panel), call it instead of redirecting
            if (typeof onSaved === 'function') {
                onSaved(data);
            } else {
                setTimeout(() => {
                    window.location.href = '/';
                }, 1500);
            }
        })
        .catch(error => {
            console.error('Error saving crop:', error);
            alert('Error saving crop: ' + error.message);
        })
        .finally(() => {
            if (saveBtn.innerHTML.includes('Saving')) {
                saveBtn.innerHTML = originalText;
                saveBtn.disabled = false;
                feather.replace();
            }
        });
    });
}
