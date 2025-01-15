document.addEventListener('DOMContentLoaded', function() {
    // ReportChat overlay handling
    const reportchatInfo = document.querySelector('.reportchat-info');
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');

    userInput.addEventListener('focus', function() {
        reportchatInfo.classList.add('hidden');
    });

    const sendButton = document.getElementById('send-button');
    const leftSidebar = document.getElementById('left-sidebar');
    const rightSidebar = document.getElementById('right-sidebar');
    const leftToggle = document.getElementById('left-toggle');
    const rightToggle = document.getElementById('right-toggle');

    // Chat functionality
    function addMessage(message, isUser = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;
        if (typeof message === 'string') {
            messageDiv.textContent = message;
        } else {
            messageDiv.appendChild(message);
        }
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function formatSQLResults(results) {
        if (!results.length) return 'No results found';
        
        // Create table header
        let table = '<div class="sql-results"><table><thead><tr>';
        const columns = Object.keys(results[0]);
        columns.forEach(column => {
            table += `<th>${column}</th>`;
        });
        table += '</tr></thead><tbody>';
        
        // Add data rows
        results.forEach(row => {
            table += '<tr>';
            columns.forEach(column => {
                table += `<td>${row[column] ?? ''}</td>`;
            });
            table += '</tr>';
        });
        
        table += '</tbody></table></div>';
        return table;
    }

    function formatErrorDetails(error, attempts) {
        const container = document.createElement('div');
        container.className = 'error-container';
        
        // Main error message
        const errorMessage = document.createElement('div');
        errorMessage.className = 'error-message';
        errorMessage.textContent = error;
        container.appendChild(errorMessage);
        
        // Attempt details if available
        if (attempts && attempts.length > 0) {
            const detailsContainer = document.createElement('div');
            detailsContainer.className = 'error-details';
            
            const toggleButton = document.createElement('button');
            toggleButton.className = 'error-details-toggle';
            toggleButton.textContent = 'Show attempt details ▼';
            
            const detailsList = document.createElement('div');
            detailsList.className = 'error-attempts hidden';
            attempts.forEach(attempt => {
                const attemptDiv = document.createElement('div');
                attemptDiv.className = 'error-attempt';
                attemptDiv.textContent = attempt;
                detailsList.appendChild(attemptDiv);
            });
            
            toggleButton.addEventListener('click', () => {
                const isHidden = detailsList.classList.contains('hidden');
                detailsList.classList.toggle('hidden');
                toggleButton.textContent = `${isHidden ? 'Hide' : 'Show'} attempt details ${isHidden ? '▲' : '▼'}`;
            });
            
            detailsContainer.appendChild(toggleButton);
            detailsContainer.appendChild(detailsList);
            container.appendChild(detailsContainer);
        }
        
        return container;
    }

    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessage(message, true);
        userInput.value = '';

        try {
            // Check if message starts with SELECT, indicating it's a direct SQL query
            if (message.toUpperCase().startsWith('SELECT')) {
                const response = await fetch('/execute_query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ query: message })
                });

                const data = await response.json();
                if (data.error) {
                    addMessage(formatErrorDetails(data.error, data.attempts), false);
                } else {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'message assistant-message';
                    let content = '';
                    
                    // Add visualization if requested
                    if (data.visualization_html) {
                        content += `
                            <div class="visualization-container">
                                <iframe 
                                    id="visualization-frame"
                                    style="width: 100%; height: 400px; border: none;"
                                    srcdoc="${data.visualization_html}"
                                ></iframe>
                            </div>`;
                    }
                    
                    // Always add results table
                    content += formatSQLResults(data.results);
                    messageDiv.innerHTML = content;
                    chatMessages.appendChild(messageDiv);
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }
            } else {
                // Translate message to SQL using Claude API
                const translateResponse = await fetch('/translate_to_sql', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: message })
                });

                const translateData = await translateResponse.json();
                if (translateData.error) {
                    addMessage(formatErrorDetails(translateData.error, translateData.attempts), false);
                    return;
                }

                // Show SQL verification with SweetAlert
                const result = await Swal.fire({
                    title: 'Generated SQL Query',
                    html: `<pre><code>${translateData.query}</code></pre>`,
                    icon: 'question',
                    showCancelButton: true,
                    confirmButtonText: 'Execute Query',
                    cancelButtonText: 'Cancel',
                    customClass: {
                        popup: 'swal-wide',
                        content: 'text-left'
                    }
                });

                if (result.isConfirmed) {
                    // Execute the generated SQL query with visualization config from backend
                    const queryResponse = await fetch('/execute_query', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ 
                            query: translateData.query,
                            visualization: translateData.visualization
                        })
                    });

                    const queryData = await queryResponse.json();
                    if (queryData.error) {
                        addMessage(formatErrorDetails(queryData.error, queryData.attempts), false);
                    } else {
                        const messageDiv = document.createElement('div');
                        messageDiv.className = 'message assistant-message';
                        
                        // Create accordion for SQL query
                        const timestamp = new Date().toLocaleString('en-US', {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                        });
                        
                        const apiCallsHtml = `
                            <div class="sql-accordion">
                                <div class="sql-accordion-header">
                                    <span>API Calls - ${timestamp}</span>
                                    <button class="sql-accordion-toggle">▼</button>
                                </div>
                                <div class="sql-accordion-content">
                                    <div class="api-call">
                                        <h4>1. SQL Generation</h4>
                                        <pre><code>${translateData.query}</code></pre>
                                    </div>
                                    ${translateData.visualization ? `
                                        <div class="api-call">
                                            <h4>2. Visualization Configuration</h4>
                                            <pre><code>${JSON.stringify(translateData.visualization, null, 2)}</code></pre>
                                        </div>
                                    ` : ''}
                                </div>
                            </div>
                        `;
                        
                        // Add accordion, visualization (if requested), and results table
                        let resultContent = '';
                        
                        // Add visualization if requested
                        if (queryData.visualization_html) {
                            resultContent += `
                                <div class="visualization-container">
                                    <iframe 
                                        id="visualization-frame"
                                        style="width: 100%; height: 400px; border: none;"
                                        srcdoc="${queryData.visualization_html}"
                                    ></iframe>
                                </div>`;
                        }
                        
                        // Always add results table
                        resultContent += formatSQLResults(queryData.results);
                        messageDiv.innerHTML = apiCallsHtml + resultContent;
                        chatMessages.appendChild(messageDiv);
                        
                        // Add click handler for accordion toggle
                        const toggle = messageDiv.querySelector('.sql-accordion-toggle');
                        const content = messageDiv.querySelector('.sql-accordion-content');
                        toggle.addEventListener('click', () => {
                            content.classList.toggle('expanded');
                            toggle.textContent = content.classList.contains('expanded') ? '▲' : '▼';
                        });
                        
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                }
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage('Sorry, there was an error processing your request.', false);
        }
    }

    // Send message on button click
    sendButton.addEventListener('click', sendMessage);

    // Send message on Enter key (but allow Shift+Enter for new lines)
    userInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });

    // Sidebar toggle functionality
    leftToggle.addEventListener('click', () => {
        leftSidebar.classList.toggle('expanded');
        const icon = leftToggle.querySelector('.toggle-icon');
        icon.textContent = leftSidebar.classList.contains('expanded') ? '❮' : '❯';
    });

    rightToggle.addEventListener('click', () => {
        rightSidebar.classList.toggle('expanded');
        const icon = rightToggle.querySelector('.toggle-icon');
        icon.textContent = rightSidebar.classList.contains('expanded') ? '❯' : '❮';
    });

    // Initialize dropzones
    const dropzoneTypes = ['IW38', 'IW68', 'IW47'];
    
    dropzoneTypes.forEach(type => {
        const dropzone = new Dropzone(`div#dropzone-${type}`, {
            paramName: 'file',
            createImageThumbnails: false,
            url: `/upload/${type}`,
            acceptedFiles: '.xlsx,.xls',
            dictDefaultMessage: `Drop ${type} Excel files here`,
            addRemoveLinks: true,
            maxFilesize: 50, // MB
            init: function() {
                this.on('success', function(file, response) {
                    // Add the new file to the list
                    const fileList = document.getElementById(`file-list-${type}`);
                    const fileItem = document.createElement('div');
                    fileItem.className = 'file-item';
                    fileItem.innerHTML = `
                        <span class="file-name">${response.filename}</span>
                        <span class="file-date">${response.lastUpdated}</span>
                    `;
                    fileList.insertBefore(fileItem, fileList.firstChild);
                    
                    // Remove the file from dropzone display
                    this.removeFile(file);

                    // Show success message in chat
                    addMessage(`File ${file.name} uploaded successfully to ${type}`, false);
                });

                this.on('error', function(file, errorMessage) {
                    console.error(`Upload error for ${file.name}:`, errorMessage);
                    // Show error message in chat
                    addMessage(`Error uploading ${file.name}: ${errorMessage.error || errorMessage}`, false);
                });
            }
        });
    });

    // Initialize background effect
    VANTA.WAVES({
        el: "#vanta-bg",
        mouseControls: true,
        touchControls: true,
        gyroControls: false,
        minHeight: 200.00,
        minWidth: 200.00,
        scale: 1.00,
        scaleMobile: 1.00,
        color: 0x6699CC,
        shininess: 60.00,
        waveHeight: 40.00,
        waveSpeed: 0.25,
        zoom: 0.75
    });
});
