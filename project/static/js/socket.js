/**
 * RealTimePoll - Socket.IO Client
 * Handles WebSocket connections for real-time poll updates
 */

(function() {
    'use strict';

    // Socket.IO configuration
    const SOCKET_OPTIONS = {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        timeout: 20000
    };

    // Global socket instance
    window.socket = null;
    window.socketConnected = false;

    /**
     * Initialize Socket.IO connection
     */
    function initSocket() {
        // Check if Socket.IO is loaded
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not loaded. Real-time updates disabled.');
            return;
        }

        // Create socket connection
        window.socket = io(SOCKET_OPTIONS);

        // Connection events
        window.socket.on('connect', function() {
            console.log('Socket connected:', window.socket.id);
            window.socketConnected = true;
            handleConnect();
        });

        window.socket.on('disconnect', function(reason) {
            console.log('Socket disconnected:', reason);
            window.socketConnected = false;
            handleDisconnect(reason);
        });

        window.socket.on('connect_error', function(error) {
            console.error('Socket connection error:', error);
            window.socketConnected = false;
        });

        // Custom events
        window.socket.on('connected', function(data) {
            console.log('Server acknowledged connection:', data);
        });

        window.socket.on('joined', function(data) {
            console.log('Joined poll room:', data.poll_code);
        });

        window.socket.on('vote_update', function(data) {
            handleVoteUpdate(data);
        });

        window.socket.on('error', function(data) {
            console.error('Socket error:', data);
            handleSocketError(data);
        });
    }

    /**
     * Handle successful connection
     */
    function handleConnect() {
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('socket:connected', {
            detail: { socketId: window.socket.id }
        }));
    }

    /**
     * Handle disconnection
     * @param {string} reason - Reason for disconnection
     */
    function handleDisconnect(reason) {
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('socket:disconnected', {
            detail: { reason: reason }
        }));
    }

    /**
     * Handle vote update from server
     * @param {Object} data - Vote update data
     */
    function handleVoteUpdate(data) {
        console.log('Received vote update:', data);

        // Check if updateResults function exists (defined in poll page)
        if (typeof updateResults === 'function') {
            updateResults(data);
        }

        // Dispatch custom event for other components
        document.dispatchEvent(new CustomEvent('poll:vote_update', {
            detail: data
        }));
    }

    /**
     * Handle socket errors
     * @param {Object} data - Error data
     */
    function handleSocketError(data) {
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('socket:error', {
            detail: data
        }));
    }

    /**
     * Join a poll room for real-time updates
     * @param {string} pollCode - The poll code to join
     */
    function joinPollRoom(pollCode) {
        if (window.socket && window.socketConnected) {
            window.socket.emit('join_poll', { poll_code: pollCode });
        }
    }

    /**
     * Leave a poll room
     * @param {string} pollCode - The poll code to leave
     */
    function leavePollRoom(pollCode) {
        if (window.socket && window.socketConnected) {
            window.socket.emit('leave_poll', { poll_code: pollCode });
        }
    }

    /**
     * Request current results for a poll
     * @param {string} pollCode - The poll code
     */
    function requestResults(pollCode) {
        if (window.socket && window.socketConnected) {
            window.socket.emit('request_results', { poll_code: pollCode });
        }
    }

    /**
     * Generate browser token if not exists
     * @returns {string} Browser token
     */
    function getOrCreateBrowserToken() {
        const TOKEN_KEY = 'rtp_browser_token';
        let token = localStorage.getItem(TOKEN_KEY);

        if (!token) {
            token = generateUUID();
            localStorage.setItem(TOKEN_KEY, token);
        }

        return token;
    }

    /**
     * Generate UUID v4
     * @returns {string} UUID string
     */
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    /**
     * Check if WebSocket is connected
     * @returns {boolean} Connection status
     */
    function isConnected() {
        return window.socketConnected;
    }

    /**
     * Get socket ID
     * @returns {string|null} Socket ID
     */
    function getSocketId() {
        return window.socket ? window.socket.id : null;
    }

    // Expose public API
    window.PollSocket = {
        init: initSocket,
        joinRoom: joinPollRoom,
        leaveRoom: leavePollRoom,
        requestResults: requestResults,
        getToken: getOrCreateBrowserToken,
        isConnected: isConnected,
        getSocketId: getSocketId
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSocket);
    } else {
        initSocket();
    }

})();
