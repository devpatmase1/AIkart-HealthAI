const STORAGE_KEY = 'biomed_chat_state';

export const saveState = (_state: any) => {
    // Intentionally no-op: state is not saved so refreshing the page resets all chats.
};

export const loadState = () => {
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch (err) {
        console.error('Could not clear stored state:', err);
    }
    return undefined;
}; 