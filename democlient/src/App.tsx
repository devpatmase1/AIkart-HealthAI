import { useEffect, useState } from 'react';
import { 
    FluentProvider, 
    webLightTheme,
    makeStyles,
} from '@fluentui/react-components';
import { useDispatch } from 'react-redux';
import Header from '@components/Header';
import ChatList from '@components/ChatList';
import ChatPanel from '@components/ChatPanel';
import LoadingSpinner from '@components/LoadingSpinner';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { setLoading, clearAllPendingResponses } from '@store/slices/chatSlice';

const useStyles = makeStyles({
    root: {
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#f4f4f4',
    },
    main: {
        display: 'flex',
        flex: 1,
        overflow: 'hidden',
        position: 'relative',
        backgroundColor: '#f4f4f4',
    },
    chatList: {
        width: '320px',
        borderRight: '1px solid rgba(226, 232, 240, 0.9)',
        zIndex: 10,
        '@media (max-width: 768px)': {
            position: 'absolute',
            top: 0,
            left: 0,
            bottom: 0,
            width: '85%',
            maxWidth: '320px',
            zIndex: 100,
            backgroundColor: 'rgba(255, 255, 255, 0.98)',
            boxShadow: '4px 0 20px rgba(0,0,0,0.08)',
            transform: 'translateX(-100%)',
            transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        },
    },
    chatListVisible: {
        '@media (max-width: 768px)': {
            transform: 'translateX(0)',
        },
    },
    overlay: {
        display: 'none',
        '@media (max-width: 768px)': {
            display: 'block',
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(15, 23, 42, 0.4)',
            backdropFilter: 'blur(4px)',
            zIndex: 99,
        },
    },
    chatPanel: {
        flex: 1,
        backgroundColor: '#f4f4f4',
    },
    loadingContainer: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: '#f4f4f4',
    }
});

function ChatPage() {
    const classes = useStyles();
    const dispatch = useDispatch();
    
    const [sidebarVisible, setSidebarVisible] = useState(false);
    const [isMobile, setIsMobile] = useState(false);
    
    const toggleSidebar = () => setSidebarVisible(!sidebarVisible);
    const handleOverlayClick = () => setSidebarVisible(false);
    
    useEffect(() => {
        const checkIfMobile = () => {
            setIsMobile(window.innerWidth <= 768);
        };
        checkIfMobile();
        window.addEventListener('resize', checkIfMobile);
        return () => window.removeEventListener('resize', checkIfMobile);
    }, []);
    
    useEffect(() => {
        dispatch(setLoading(false));
        dispatch(clearAllPendingResponses());
    }, [dispatch]);
    
    return (
        <div className={classes.root}>
            <Header toggleSidebar={toggleSidebar} isMobile={isMobile} />
            <main className={classes.main}>
                {sidebarVisible && isMobile && (
                    <div className={classes.overlay} onClick={handleOverlayClick} />
                )}
                
                <div className={`${classes.chatList} ${sidebarVisible ? classes.chatListVisible : ''}`}>
                    <ChatList onSelectChat={isMobile ? handleOverlayClick : undefined} />
                </div>
                
                <div className={classes.chatPanel}>
                    <ChatPanel />
                </div>
            </main>
        </div>
    );
}

function AppContent() {
    const classes = useStyles();
    const { loading, error } = useAuth();

    if (loading) {
        return (
            <div className={classes.loadingContainer}>
                <LoadingSpinner label="Loading authentication..." />
            </div>
        );
    }

    if (error) {
        return (
            <div className={classes.loadingContainer}>
                <p>Authentication error: {error}</p>
                <p>Please refresh the page or try again later.</p>
            </div>
        );
    }

    return <ChatPage />;
}

export default function App() {
    return (
        <FluentProvider theme={webLightTheme}>
            <AuthProvider>
                <AppContent />
            </AuthProvider>
        </FluentProvider>
    );
}
