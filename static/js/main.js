// Quenex Main JavaScript - Orange & White Theme

// Auto-hide alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    // Flash message auto-hide
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        }, 5000);
    });

    // Add fade-in animation to cards
    const cards = document.querySelectorAll('.card, .event-card, .category-card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.classList.add('fade-in-up');
        }, index * 100);
    });

    // Mobile menu close on click
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (navbarCollapse.classList.contains('show')) {
                navbarCollapse.classList.remove('show');
            }
        });
    });
});

// Search functionality
function searchEvents() {
    const searchTerm = document.getElementById('searchInput')?.value;
    if (searchTerm && searchTerm.trim()) {
        window.location.href = `/events?search=${encodeURIComponent(searchTerm)}`;
    }
    return false;
}

// Filter events by category
function filterByCategory(category) {
    window.location.href = `/events?category=${category}`;
}

// Filter events by date
function filterByDate() {
    const date = document.getElementById('dateFilter')?.value;
    if (date) {
        window.location.href = `/events?date=${date}`;
    }
}

// Confirm booking
function confirmBooking(eventId) {
    if (confirm('Are you sure you want to book this event?')) {
        document.getElementById(`booking-form-${eventId}`).submit();
    }
}

// Mobile Money payment validation
function validateMobileMoney(number) {
    // Uganda mobile money format: 256XXXXXXXXX or 07XXXXXXXXX
    const ugandaRegex = /^(256|0)[7-9][0-9]{8}$/;
    return ugandaRegex.test(number);
}

// Format currency (UGX)
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-UG', {
        style: 'currency',
        currency: 'UGX',
        minimumFractionDigits: 0
    }).format(amount);
}

// Format date
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('en-UG', options);
}

// Print ticket
function printTicket(ticketId) {
    const printContent = document.getElementById(`ticket-${ticketId}`).cloneNode(true);
    const printWindow = window.open('', '_blank');
    
    printWindow.document.write(`
        <html>
        <head>
            <title>Quenex Ticket</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body { padding: 20px; font-family: Arial, sans-serif; }
                .ticket-container { max-width: 800px; margin: 0 auto; }
                .ticket-header { background: #F39C12; color: white; padding: 20px; text-align: center; }
                .ticket-body { padding: 20px; border: 1px solid #ddd; }
                .qr-code { text-align: center; margin: 20px 0; }
                @media print {
                    .no-print { display: none; }
                    button { display: none; }
                }
            </style>
        </head>
        <body>
            <div class="ticket-container">
                ${printContent.outerHTML}
            </div>
            <div class="text-center mt-4 no-print">
                <button onclick="window.print()" class="btn btn-primary">Print Ticket</button>
                <button onclick="window.close()" class="btn btn-secondary">Close</button>
            </div>
        </body>
        </html>
    `);
    printWindow.document.close();
}

// Download QR Code
function downloadQR(elementId, filename = 'ticket-qr.png') {
    const imgElement = document.getElementById(elementId);
    if (imgElement) {
        const link = document.createElement('a');
        link.download = filename;
        link.href = imgElement.src;
        link.click();
    }
}

// Check ticket availability via AJAX
async function checkTicketAvailability(eventId, ticketType, quantity) {
    try {
        const response = await fetch(`/api/event/${eventId}/check-availability?ticket_type=${ticketType}&quantity=${quantity}`);
        const data = await response.json();
        
        const availabilityMsg = document.getElementById('availabilityMsg');
        if (availabilityMsg) {
            if (data.available) {
                availabilityMsg.innerHTML = `<span class="text-success">✓ ${data.remaining} tickets available</span>`;
                availabilityMsg.className = 'text-success';
            } else {
                availabilityMsg.innerHTML = `<span class="text-danger">✗ Only ${data.remaining} tickets available</span>`;
                availabilityMsg.className = 'text-danger';
            }
        }
        return data.available;
    } catch (error) {
        console.error('Error checking availability:', error);
        return false;
    }
}

// Update ticket price display
function updateTicketPrice(selectElement) {
    const selectedOption = selectElement.options[selectElement.selectedIndex];
    const price = selectedOption.getAttribute('data-price');
    const priceDisplay = document.getElementById('selectedPrice');
    if (priceDisplay) {
        priceDisplay.innerText = formatCurrency(parseFloat(price));
    }
}

// Validate payment form
function validatePaymentForm() {
    const mobileNumber = document.getElementById('mobile_money_number')?.value;
    if (mobileNumber && !validateMobileMoney(mobileNumber)) {
        alert('Please enter a valid Mobile Money number (e.g., 2567XXXXXXXX or 07XXXXXXXX)');
        return false;
    }
    return true;
}

// Copy to clipboard
function copyToClipboard(text, elementId) {
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById(elementId);
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
        setTimeout(() => {
            btn.innerHTML = originalText;
        }, 2000);
    });
}

// Load more events (pagination)
let currentPage = 1;
function loadMoreEvents() {
    currentPage++;
    const container = document.getElementById('eventsContainer');
    const loadingIndicator = document.getElementById('loadingIndicator');
    
    loadingIndicator.style.display = 'block';
    
    fetch(`/api/events?page=${currentPage}`)
        .then(response => response.json())
        .then(data => {
            if (data.events.length > 0) {
                data.events.forEach(event => {
                    container.appendChild(createEventCard(event));
                });
            } else {
                document.getElementById('loadMoreBtn').style.display = 'none';
            }
            loadingIndicator.style.display = 'none';
        })
        .catch(error => {
            console.error('Error loading events:', error);
            loadingIndicator.style.display = 'none';
        });
}

// Create event card dynamically
function createEventCard(event) {
    const col = document.createElement('div');
    col.className = 'col-md-4 mb-4';
    col.innerHTML = `
        <div class="card event-card h-100">
            <img src="/static/uploads/${event.image}" class="card-img-top" alt="${event.title}">
            <div class="card-body">
                <span class="badge bg-primary mb-2">${event.category_name}</span>
                <h5 class="card-title">${event.title}</h5>
                <p class="card-text text-muted">
                    <i class="fas fa-calendar"></i> ${formatDate(event.date)}<br>
                    <i class="fas fa-map-marker-alt"></i> ${event.venue.substring(0, 50)}<br>
                    <i class="fas fa-clock"></i> ${event.time}
                </p>
                <a href="/event/${event.id}" class="btn btn-primary-custom w-100">View Details</a>
            </div>
        </div>
    `;
    return col;
}

// Smooth scroll to top
function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Show/hide password toggle
function togglePassword(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// Initialize tooltips
var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});

// Event listener for ESC key to close modals
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const openModals = document.querySelectorAll('.modal.show');
        openModals.forEach(modal => {
            const modalInstance = bootstrap.Modal.getInstance(modal);
            modalInstance.hide();
        });
    }
});

// Export data to CSV
function exportToCSV(data, filename = 'export.csv') {
    const csvRows = [];
    const headers = Object.keys(data[0]);
    csvRows.push(headers.join(','));
    
    for (const row of data) {
        const values = headers.map(header => {
            const val = row[header];
            return `"${String(val).replace(/"/g, '""')}"`;
        });
        csvRows.push(values.join(','));
    }
    
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
}