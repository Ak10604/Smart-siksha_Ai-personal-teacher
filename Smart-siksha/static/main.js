// Main JavaScript file for Educational Video App

// Global utility functions
function showLoading(elementId) {
  const element = document.getElementById(elementId)
  if (element) {
    element.innerHTML = `
            <div class="text-center">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">Please wait...</p>
            </div>
        `
  }
}

function hideLoading(elementId) {
  const element = document.getElementById(elementId)
  if (element) {
    element.innerHTML = ""
  }
}

function showMessage(message, type = "info") {
  const alertClass = type === "error" ? "alert-danger" : type === "success" ? "alert-success" : "alert-info"

  const alertDiv = document.createElement("div")
  alertDiv.className = `alert ${alertClass} alert-dismissible fade show`
  alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `

  // Insert at top of main content
  const main = document.querySelector("main")
  if (main) {
    main.insertBefore(alertDiv, main.firstChild)

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
      if (alertDiv.parentNode) {
        alertDiv.remove()
      }
    }, 5000)
  }
}

// API helper functions
async function makeRequest(url, options = {}) {
  try {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.error || "Request failed")
    }

    return data
  } catch (error) {
    console.error("Request error:", error)
    throw error
  }
}

// Form validation helpers
function validateEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return re.test(email)
}

function validatePassword(password) {
  return password.length >= 6
}

// Progress tracking utilities
function updateProgressBar(elementId, progress, message = "") {
  const progressBar = document.getElementById(elementId)
  if (progressBar) {
    progressBar.style.width = progress + "%"
    progressBar.setAttribute("aria-valuenow", progress)
    progressBar.textContent = progress + "%"
  }

  if (message) {
    const messageElement = document.getElementById(elementId + "_message")
    if (messageElement) {
      messageElement.textContent = message
    }
  }
}

// Local storage helpers
function saveToStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch (error) {
    console.error("Storage save error:", error)
  }
}

function loadFromStorage(key) {
  try {
    const item = localStorage.getItem(key)
    return item ? JSON.parse(item) : null
  } catch (error) {
    console.error("Storage load error:", error)
    return null
  }
}

// Initialize app when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  // Initialize tooltips if Bootstrap is available
  const bootstrap = window.bootstrap // Declare the bootstrap variable
  if (typeof bootstrap !== "undefined") {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    tooltipTriggerList.map((tooltipTriggerEl) => new bootstrap.Tooltip(tooltipTriggerEl))
  }

  // Add smooth scrolling to anchor links
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault()
      const target = document.querySelector(this.getAttribute("href"))
      if (target) {
        target.scrollIntoView({
          behavior: "smooth",
        })
      }
    })
  })

  // Auto-focus first input in forms
  const firstInput = document.querySelector('form input:not([type="hidden"])')
  if (firstInput) {
    firstInput.focus()
  }
})

// Error handling
window.addEventListener("error", (e) => {
  console.error("Global error:", e.error)
  showMessage("An unexpected error occurred. Please refresh the page.", "error")
})

// Network status monitoring
window.addEventListener("online", () => {
  showMessage("Connection restored", "success")
})

window.addEventListener("offline", () => {
  showMessage("Connection lost. Some features may not work.", "error")
})
