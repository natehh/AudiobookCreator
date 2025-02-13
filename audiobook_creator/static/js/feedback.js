document.addEventListener("DOMContentLoaded", function() {
  // Inject custom styles for the feedback UI
  const style = document.createElement('style');
  style.innerHTML = `
    /* Style for feedback button */
    #feedback-button {
      position: fixed;
      bottom: 20px;
      right: 20px;
      width: 40px;
      height: 40px;
      background: #007bff;
      color: #fff;
      border-radius: 50%;
      text-align: center;
      line-height: 40px;
      cursor: pointer;
      z-index: 1000;
      font-size: 24px; /* Increased font size for emoji */
    }
    /* Style for modal overlay */
    #feedback-modal-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: flex-end;  /* Align modal to bottom */
      justify-content: flex-end; /* Align modal to right */
      z-index: 1001;
    }
    /* Style for modal */
    #feedback-modal {
      position: fixed;
      bottom: 60px; /* Appear above the feedback button */
      right: 20px;
      background: #fff;
      color: black; /* Message text is black */
      padding: 20px;
      border-radius: 5px;
      max-width: 400px;
      width: 300px;
    }
    /* Close button */
    #feedback-modal-close {
      position: absolute;
      top: 10px;
      right: 10px;
      font-size: 20px;
      cursor: pointer;
    }
    /* Textarea style */
    #feedback-message {
      width: 100%;
      height: 100px;
      margin-bottom: 10px;
    }
    /* Email input style */
    #feedback-email {
      width: 100%;
      margin-bottom: 10px;
    }
  `;
  document.head.appendChild(style);

  // Create feedback button
  const feedbackButton = document.createElement('div');
  feedbackButton.id = 'feedback-button';
  // Use mail emoji that fills the whole circle
  feedbackButton.innerHTML = '📧';
  document.body.appendChild(feedbackButton);

  // Create the feedback modal overlay with popup
  const modalOverlay = document.createElement('div');
  modalOverlay.id = 'feedback-modal-overlay';
  modalOverlay.style.display = 'none';
  modalOverlay.innerHTML = `
    <div id="feedback-modal">
      <span id="feedback-modal-close">&times;</span>
      <p>We want to hear from you! Please send a message with bugs, feedback, feature requests, or anything else you want us to know!</p>
      <textarea id="feedback-message" placeholder="Your message..."></textarea>
      <div>
        <input type="checkbox" id="include-email" name="include-email">
        <label for="include-email">Include my email for a reply</label>
      </div>
      <input type="email" id="feedback-email" placeholder="Your email (optional)" style="display: none;">
      <button id="feedback-send">Send</button>
    </div>
  `;
  document.body.appendChild(modalOverlay);

  // Show modal on feedback button click
  feedbackButton.addEventListener('click', function() {
    modalOverlay.style.display = 'block';
  });

  // Hide modal when close button is clicked
  document.getElementById('feedback-modal-close').addEventListener('click', function() {
    modalOverlay.style.display = 'none';
  });

  // Dismiss popup when clicking outside the modal
  modalOverlay.addEventListener('click', function(e) {
    if (e.target === modalOverlay) {
      modalOverlay.style.display = 'none';
    }
  });

  // Toggle email input if checkbox is toggled
  const includeEmailCheckbox = document.getElementById('include-email');
  const feedbackEmailField = document.getElementById('feedback-email');
  includeEmailCheckbox.addEventListener('change', function() {
    if (includeEmailCheckbox.checked) {
      feedbackEmailField.style.display = 'block';
    } else {
      feedbackEmailField.style.display = 'none';
    }
  });

  // Handle send feedback
  document.getElementById('feedback-send').addEventListener('click', function() {
    const message = document.getElementById('feedback-message').value.trim();
    const includeEmail = includeEmailCheckbox.checked;
    const email = includeEmail ? document.getElementById('feedback-email').value.trim() : '';
    
    if (!message) {
      alert("Please enter a message.");
      return;
    }

    const payload = {
      message: message,
      includeEmail: includeEmail,
      email: email
    };

    fetch('/send-feedback', {
      method: 'POST',
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    }).then(function(response) {
      if (response.ok) {
        alert("Feedback sent! Thank you.");
        document.getElementById('feedback-message').value = "";
        if (includeEmail) {
          document.getElementById('feedback-email').value = "";
          includeEmailCheckbox.checked = false;
          feedbackEmailField.style.display = 'none';
        }
        modalOverlay.style.display = 'none';
      } else {
        alert("There was an error sending your feedback. Please try again later.");
      }
    }).catch(function(error) {
      console.error("Error sending feedback:", error);
      alert("There was an error sending your feedback. Please try again later.");
    });
  });
}); 