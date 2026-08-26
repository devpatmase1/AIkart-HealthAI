import React from 'react';
import { makeStyles, Text, mergeClasses } from '@fluentui/react-components';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSelector } from 'react-redux';
import type { Message } from '../types';
import { RootState } from '../store/store';

const AnimationStyles = () => (
  <style>
    {`
    @keyframes pulseDot {
      0%, 100% { opacity: 0.3; transform: scale(0.8); }
      50% { opacity: 1; transform: scale(1.1); }
    }
    .dot1 { animation: pulseDot 1.4s infinite ease-in-out 0s; }
    .dot2 { animation: pulseDot 1.4s infinite ease-in-out 0.2s; }
    .dot3 { animation: pulseDot 1.4s infinite ease-in-out 0.4s; }
    .pulse-dot {
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background-color: #0050FF;
      margin: 0 3px;
    }
    `}
  </style>
);

const useStyles = makeStyles({
    container: {
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
        padding: '1rem',
        maxWidth: '900px',
        margin: '0 auto',
        width: '100%',
    },
    messageGroupLeft: {
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '85%',
        alignSelf: 'flex-start',
    },
    loadingDot: {
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '85%',
        alignSelf: 'flex-start',
    },
    messageGroupRight: {
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '80%',
        alignSelf: 'flex-end',
    },
    sender: {
        fontSize: '0.8rem',
        fontWeight: 600,
        color: '#475569',
        marginBottom: '6px',
        paddingLeft: '0.5rem',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
    },
    message: {
        padding: '0.9rem 1.25rem',
        borderRadius: '20px',
        width: 'fit-content',
        maxWidth: '100%',
        wordWrap: 'break-word',
        boxShadow: '0 4px 16px rgba(0, 0, 0, 0.03)',
        transition: 'all 0.2s ease',
        lineHeight: '1.5',
    },
    userMessage: {
        backgroundColor: '#0050FF',
        color: '#ffffff',
        borderBottomRightRadius: '6px',
        boxShadow: '0 4px 16px rgba(0, 80, 255, 0.25)',
    },
    botMessage: {
        backgroundColor: 'rgba(255, 255, 255, 0.92)',
        backdropFilter: 'blur(20px)',
        color: '#0f172a',
        border: '1px solid rgba(226, 232, 240, 0.9)',
        borderBottomLeftRadius: '6px',
    },
    loadingMessage: {
        borderRadius: '20px',
        borderBottomLeftRadius: '6px',
        backgroundColor: 'rgba(255, 255, 255, 0.92)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(226, 232, 240, 0.9)',
        padding: '0.75rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
    },
    loadingDots: {
        display: 'flex',
        alignItems: 'center',
        gap: '2px',
    },
    markdownContainer: {
        '& p': {
            margin: '0 0 0.75rem 0',
            '&:last-child': {
                marginBottom: 0,
            }
        },
        '& h1, & h2, & h3, & h4': {
            marginTop: '0.5rem',
            marginBottom: '0.5rem',
            color: '#0f172a',
            fontWeight: 700,
        },
        '& ul, & ol': {
            paddingLeft: '1.25rem',
            marginBottom: '0.75rem',
        },
        '& code': {
            backgroundColor: 'rgba(0, 80, 255, 0.08)',
            color: '#0050FF',
            padding: '0.15rem 0.4rem',
            borderRadius: '6px',
            fontFamily: 'monospace',
            fontSize: '0.85em',
        },
        '& pre': {
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            padding: '0.85rem 1rem',
            borderRadius: '12px',
            overflowX: 'auto',
            '& code': {
                backgroundColor: 'transparent',
                color: 'inherit',
                padding: 0,
            }
        },
        '& blockquote': {
            marginLeft: '0',
            paddingLeft: '0.75rem',
            borderLeft: '3px solid #0050FF',
            color: '#475569',
        },
        '& a': {
            color: '#0050FF',
            textDecoration: 'none',
            fontWeight: 600,
            '&:hover': {
                textDecoration: 'underline',
            }
        },
        '& table': {
            borderCollapse: 'collapse',
            width: '100%',
            margin: '0.75rem 0',
            fontSize: '0.9em',
            '& th, & td': {
                border: '1px solid rgba(226, 232, 240, 0.9)',
                padding: '0.4rem 0.6rem',
                textAlign: 'left',
            },
            '& th': {
                backgroundColor: 'rgba(241, 245, 249, 0.8)',
                fontWeight: 600,
            },
        },
    },
    userMarkdownContainer: {
        '& blockquote': {
            borderLeftColor: 'rgba(255, 255, 255, 0.6)',
            color: 'rgba(255, 255, 255, 0.9)',
        },
        '& code': {
            backgroundColor: 'rgba(255, 255, 255, 0.2)',
            color: '#ffffff',
        },
        '& a': {
            color: '#ffffff',
            textDecoration: 'underline',
        },
        '& table th, & table td': {
            border: '1px solid rgba(255, 255, 255, 0.3)',
        },
        '& table th': {
            backgroundColor: 'rgba(255, 255, 255, 0.2)',
        },
    },
});

const LoadingDots = () => {
    return (
        <div style={{ display: 'flex', alignItems: 'center' }}>
            <span className="pulse-dot dot1"></span>
            <span className="pulse-dot dot2"></span>
            <span className="pulse-dot dot3"></span>
        </div>
    );
};

interface MessageListProps {
    messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
    const styles = useStyles();
    const isLoading = useSelector((state: RootState) => state.chat.isLoading);
    const pendingResponses = useSelector((state: RootState) => state.chat.pendingResponses);
    
    const renderMessageContent = (content: string, isBot: boolean) => {
        if (!content || typeof content !== 'string') return '';
        
        return (
            <div className={mergeClasses(
                styles.markdownContainer,
                !isBot ? styles.userMarkdownContainer : undefined
            )}>
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                        a: ({ node, ...props }) => (
                            <a 
                                {...props} 
                                target="_blank" 
                                rel="noopener noreferrer"
                            />
                        )
                    }}
                >
                    {content}
                </ReactMarkdown>
            </div>
        );
    };
    
    return (
        <div className={styles.container}>
            <AnimationStyles />
            
            {messages && messages.map(message => {
                if (!message || typeof message !== 'object') return null;
                const isBot = message.isBot === true;
                
                return (
                    <div 
                        key={message.id || `msg-${Math.random()}`} 
                        className={isBot ? styles.messageGroupLeft : styles.messageGroupRight}
                    >
                        <Text className={styles.sender}>
                            {isBot && <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#0050FF', display: 'inline-block' }}></span>}
                            {message.sender || ''}
                        </Text>
                        <div
                            className={mergeClasses(
                                styles.message,
                                isBot ? styles.botMessage : styles.userMessage
                            )}
                        >
                            {renderMessageContent(message.content || '', isBot)}
                        </div>
                    </div>
                );
            })}
            
            {isLoading === true && pendingResponses && Array.isArray(pendingResponses) && pendingResponses.length > 0 && 
                pendingResponses.map((pendingResponse, index) => {
                    if (!pendingResponse) return null;
                    return (
                        <div key={`loading-${index}`} className={styles.loadingDot}>
                            <Text className={styles.sender}>
                                <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#0050FF', display: 'inline-block' }}></span>
                                {pendingResponse.targetAgent || 'Agent'}
                            </Text>
                            <div className={styles.loadingMessage}>
                                <LoadingDots />
                            </div>
                        </div>
                    );
                })
            }
            
            {isLoading === true && (!pendingResponses || !Array.isArray(pendingResponses) || pendingResponses.length === 0) && (
                <div className={styles.loadingDot}>
                    <Text className={styles.sender}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#0050FF', display: 'inline-block' }}></span>
                        Orchestrator
                    </Text>
                    <div className={styles.loadingMessage}>
                        <LoadingDots />
                    </div>
                </div>
            )}
        </div>
    );
}
