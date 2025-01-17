document.addEventListener('DOMContentLoaded', function() {
    // Check for required external libraries
    if (typeof Dropzone === 'undefined') {
        console.error('Dropzone library not loaded');
        return;
    }
    if (typeof Swal === 'undefined') {
        console.error('SweetAlert2 library not loaded');
        return;
    }

    // ReportChat overlay handling with null checks
    const reportchatInfo = document.querySelector('.reportchat-info');
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const oldestFileInfo = document.getElementById('oldest-file-info');
    const refreshButton = document.getElementById('refresh-sap-data');

    // Validate required DOM elements
    if (!chatMessages || !userInput || !oldestFileInfo || !refreshButton) {
        console.error('Required DOM elements not found');
        return;
    }

    // Function to fetch and display oldest file info with timeout
    async function updateOldestFileInfo() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout

            const response = await fetch('/get_oldest_file', {
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            const data = await response.json();
            
            if (data.error) {
                oldestFileInfo.innerHTML = `<p>No files found in datalake</p>`;
            } else {
                oldestFileInfo.innerHTML = `
                    <p><strong>Oldest file:</strong> ${data.name}</p>
                    <p><strong>Type:</strong> ${data.type}</p>
                    <p><strong>Last modified:</strong> ${data.last_modified}</p>
                    <p><strong>Days since update:</strong> ${data.days_old}</p>
                `;
            }
        } catch (error) {
            console.error('Error fetching oldest file info:', error);
            oldestFileInfo.innerHTML = `<p>Error loading file information</p>`;
        }
    }

    // Function to handle refresh button click
    async function handleRefresh() {
        try {
            refreshButton.disabled = true;
            const response = await fetch('/refresh_sap_data', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.error) {
                Swal.fire({
                    title: 'Error',
                    text: data.error,
                    icon: 'error'
                });
            } else {
                Swal.fire({
                    title: 'Success',
                    text: data.message,
                    icon: 'success'
                });
                // Update the file info after successful refresh
                updateOldestFileInfo();
            }
        } catch (error) {
            console.error('Error refreshing SAP data:', error);
            Swal.fire({
                title: 'Error',
                text: 'Failed to refresh SAP data',
                icon: 'error'
            });
        } finally {
            refreshButton.disabled = false;
        }
    }

    // Add click handler for refresh button
    refreshButton.addEventListener('click', handleRefresh);

    // Initial load of oldest file info
    updateOldestFileInfo();
    
    // Initialize right sidebar as expanded
    const rightSidebar = document.getElementById('right-sidebar');
    rightSidebar.classList.add('expanded');
    const rightToggleIcon = document.querySelector('#right-toggle .toggle-icon');
    if (rightToggleIcon) {
        rightToggleIcon.textContent = '❯';
    }

    userInput.addEventListener('focus', function() {
        reportchatInfo.classList.add('hidden');
    });

    const sendButton = document.getElementById('send-button');
    const leftSidebar = document.getElementById('left-sidebar');
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
                    // Clone the response template
                    const template = document.getElementById('chat-response-template');
                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'message assistant-message';
                    messageDiv.appendChild(template.content.cloneNode(true));

                    // Set management summary for direct SQL
                    const managementSummary = messageDiv.querySelector('.management-summary');
                    managementSummary.innerHTML = '<p>Direct SQL Query Results</p>';
                    
                    // Set comprehensive analysis
                    const comprehensiveAnalysis = messageDiv.querySelector('.comprehensive-analysis');
                    comprehensiveAnalysis.innerHTML = `<p>Executing SQL query: ${message}</p>`;

                    // Set API calls
                    const apiCalls = messageDiv.querySelector('.api-calls');
                    apiCalls.innerHTML = `
                        <div class="api-call">
                            <h4>Direct SQL Query</h4>
                            <pre><code>${message}</code></pre>
                        </div>
                    `;

                    // Add visualization if available
                    if (data.visualization?.html) {
                        const resultsDiv = messageDiv.querySelector('.sql-results');
                        resultsDiv.insertAdjacentHTML('beforebegin', `
                            <div class="visualization-container">
                                <iframe 
                                    id="visualization-frame"
                                    style="width: 100%; height: 400px; border: none;"
                                    srcdoc="${data.visualization.html.replace(/"/g, '&quot;')}"
                                ></iframe>
                            </div>
                        `);
                    }

                    // Set results table
                    const resultsTable = messageDiv.querySelector('.sql-results table');
                    resultsTable.innerHTML = formatSQLResults(data.results);

                    // Add the message to chat
                    chatMessages.appendChild(messageDiv);

                    // Add click handlers for all accordions
                    messageDiv.querySelectorAll('.sql-accordion-header').forEach(header => {
                        const toggle = header.querySelector('.sql-accordion-toggle');
                        const content = header.nextElementSibling;
                        header.addEventListener('click', () => {
                            content.classList.toggle('expanded');
                            toggle.textContent = content.classList.contains('expanded') ? '▲' : '▼';
                        });
                    });

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
                            visualization_type: translateData.visualization_type
                        })
                    });

                    let queryData = await queryResponse.json();
                    try {
                        if (queryData.error) {
                            addMessage(formatErrorDetails(queryData.error, queryData.attempts), false);
                            return;
                        }
                        
                        // Clone the response template
                        const template = document.getElementById('chat-response-template');
                        const messageDiv = document.createElement('div');
                        messageDiv.className = 'message assistant-message';
                        messageDiv.appendChild(template.content.cloneNode(true));

                        // Set summaries from HTML
                        const managementSummary = messageDiv.querySelector('.management-summary');
                        const comprehensiveAnalysis = messageDiv.querySelector('.comprehensive-analysis');
                        
                        if (queryData.summaries) {
                            // Create a temporary container to parse the HTML
                            const tempDiv = document.createElement('div');
                            tempDiv.innerHTML = queryData.summaries;
                            
                            // Extract summaries from the parsed HTML
                            const managementContent = tempDiv.querySelector('.management-summary p')?.textContent;
                            const analysisContent = tempDiv.querySelector('.comprehensive-summary p')?.textContent;
                            
                            // Set the content
                            managementSummary.innerHTML = `<p>${managementContent || 'Management summary not available.'}</p>`;
                            comprehensiveAnalysis.innerHTML = `<p>${analysisContent || 'Comprehensive analysis not available.'}</p>`;
                        } else {
                            managementSummary.innerHTML = '<p>Management summary not available.</p>';
                            comprehensiveAnalysis.innerHTML = '<p>Comprehensive analysis not available.</p>';
                        }

                        // Set API calls
                        const apiCalls = messageDiv.querySelector('.api-calls');
                        apiCalls.innerHTML = `
                            <div class="api-call">
                                <h4>1. SQL Generation</h4>
                                <pre><code>${translateData.query}</code></pre>
                            </div>
                            ${translateData.visualization_type ? `
                                <div class="api-call">
                                    <h4>2. Visualization Type</h4>
                                    <pre><code>${translateData.visualization_type}</code></pre>
                                </div>
                            ` : ''}
                        `;

                        // Add visualization if available
                        if (queryData.visualization?.html) {
                            const resultsDiv = messageDiv.querySelector('.sql-results');
                            resultsDiv.insertAdjacentHTML('beforebegin', `
                                <div class="visualization-container">
                                    <iframe 
                                        id="visualization-frame"
                                        style="width: 100%; height: 400px; border: none;"
                                        srcdoc="${queryData.visualization.html.replace(/"/g, '&quot;')}"
                                    ></iframe>
                                </div>
                            `);
                        }

                        // Set results table
                        const resultsTable = messageDiv.querySelector('.sql-results table');
                        resultsTable.innerHTML = formatSQLResults(queryData.results);

                        // Add the message to chat
                        chatMessages.appendChild(messageDiv);

                        // Add click handlers for all accordions
                        messageDiv.querySelectorAll('.sql-accordion-header').forEach(header => {
                            const toggle = header.querySelector('.sql-accordion-toggle');
                            const content = header.nextElementSibling;
                            header.addEventListener('click', () => {
                                content.classList.toggle('expanded');
                                toggle.textContent = content.classList.contains('expanded') ? '▲' : '▼';
                            });
                        });
                        
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    } catch (error) {
                        console.error('Error processing query data:', error);
                        addMessage('Error processing query results', false);
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
    function adjustTextareaHeight(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = textarea.scrollHeight + 'px';
    }

    userInput.addEventListener('input', function() {
        adjustTextareaHeight(this);
    });

    // Initial height adjustment and on focus
    adjustTextareaHeight(userInput);
    userInput.addEventListener('focus', function() {
        adjustTextareaHeight(this);
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

    // Example cards click handling
    const exampleCards = document.querySelectorAll('.example-card');
    exampleCards.forEach(card => {
        card.addEventListener('click', function() {
            const exampleText = this.querySelector('p').textContent;
            // Remove the quotes from the example text
            userInput.value = exampleText.replace(/['"]/g, '');
            // Hide the reportchat info since we're using the input
            reportchatInfo.classList.add('hidden');
            // Focus the input
            userInput.focus();
        });
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
                        <div class="file-info">
                            <span class="file-name">${response.filename}</span>
                            <span class="file-date">${response.lastUpdated}</span>
                        </div>
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

    // Initialize database table accordions
    const tableHeaders = document.querySelectorAll('.table-header');
    tableHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const content = header.nextElementSibling;
            const toggle = header.querySelector('.table-toggle');
            content.classList.toggle('expanded');
            toggle.textContent = content.classList.contains('expanded') ? '▲' : '▼';
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
        color: 0x216EA3,
        shininess: 60.00,
        waveHeight: 40.00,
        waveSpeed: 0.25,
        zoom: 0.75
    });
});
