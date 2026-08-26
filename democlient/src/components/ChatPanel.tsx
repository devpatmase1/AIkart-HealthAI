import { useState, useRef, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
    makeStyles,
    Input,
    Button
} from '@fluentui/react-components';
import { Send24Regular, Sparkle24Regular } from '@fluentui/react-icons';
import { RootState } from '../store/store';
import { addMessage, setLoading, addPendingResponse, removePendingResponse } from '../store/slices/chatSlice';
import { api } from '../services/api';
import MessageList from './MessageList';
import MentionAutocomplete from './MentionAutocomplete';
import BrandMark from './BrandMark';
import { parseMentions, getTargetAgent } from '../utils/messageParsing';
import { v4 as uuidv4 } from 'uuid';

const useStyles = makeStyles({
    container: {
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        position: 'relative',
        backgroundColor: '#f4f4f4',
    },
    messageContainer: {
        flex: 1,
        overflow: 'auto',
        padding: '1.5rem',
        paddingBottom: '6.5rem',
        '@media (max-width: 768px)': {
            paddingBottom: '9.5rem',
        }
    },
    welcomeContainer: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '65vh',
        textAlign: 'center',
        padding: '2rem 1rem',
        gap: '1.5rem',
    },
    welcomeTitle: {
        fontSize: '2.5rem',
        fontWeight: '800',
        letterSpacing: '-0.03em',
        margin: '0.5rem 0',
        lineHeight: '1.3',
        padding: '4px 8px',
    },
    welcomeSubtitle: {
        fontSize: '1.05rem',
        color: '#475569',
        maxWidth: '520px',
        lineHeight: '1.6',
    },
    quickPromptsGrid: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: '0.75rem',
        justifyContent: 'center',
        maxWidth: '680px',
        marginTop: '1rem',
    },
    quickPromptChip: {
        borderRadius: '9999px',
        padding: '10px 18px',
        fontSize: '0.9rem',
        fontWeight: '500',
        color: '#0f172a',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
    },
    inputContainer: {
        display: 'flex',
        flexDirection: 'column',
        padding: '0.75rem 1.25rem 1.25rem 1.25rem',
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 10,
        maxWidth: '860px',
        margin: '0 auto',
        '@media (max-width: 768px)': {
            padding: '0.75rem',
            paddingBottom: 'env(safe-area-inset-bottom, 1rem)',
        }
    },
    inputRowWrapper: {
        borderRadius: '28px',
        padding: '6px 8px 6px 16px',
        boxShadow: '0 10px 30px rgba(0, 80, 255, 0.06)',
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
    },
    input: {
        flex: 1,
        backgroundColor: 'transparent',
        '& input': {
            backgroundColor: 'transparent !important',
            outline: 'none !important',
            fontSize: '0.98rem',
            color: '#0f172a',
            padding: '8px 0',
        },
        '& input::placeholder': {
            color: '#94a3b8',
        }
    },
    sendButton: {
        borderRadius: '9999px',
        backgroundColor: '#0050FF',
        color: '#ffffff',
        fontWeight: '600',
        padding: '8px 20px',
        height: '42px',
        boxShadow: '0 4px 14px rgba(0, 80, 255, 0.3)',
        '&:hover': {
            backgroundColor: '#0044db',
            color: '#ffffff',
            transform: 'scale(1.03)',
            boxShadow: '0 6px 18px rgba(0, 80, 255, 0.4)',
        },
    },
    sendButtonText: {
        marginLeft: '4px',
        '@media (max-width: 768px)': {
            display: 'none'
        }
    }
});

export default function ChatPanel() {
    const classes = useStyles();
    const dispatch = useDispatch();
    const [message, setMessage] = useState('');
    const messageContainerRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const selectedChatId = useSelector((state: RootState) => state.chat.selectedChatId);
    const selectedChat = useSelector((state: RootState) => 
        state.chat.chats.find(chat => chat.id === selectedChatId)
    );
    const pendingResponses = useSelector((state: RootState) => state.chat.pendingResponses);
    const user = useSelector((state: RootState) => state.auth.user);
    const availableAgents = useSelector((state: RootState) => state.agent.availableAgents);
    
    const [showAutocomplete, setShowAutocomplete] = useState(false);
    const [autocompletePosition, setAutocompletePosition] = useState({ top: 0, left: 0 });
    const [mentionQuery, setMentionQuery] = useState('');
    const [hasMention, setHasMention] = useState(false);

    useEffect(() => {
        dispatch(setLoading(false));
        dispatch({ type: 'chat/clearAllPendingResponses' });
    }, [dispatch]);

    useEffect(() => {
        if (pendingResponses === undefined) {
            dispatch({ type: 'chat/clearAllPendingResponses' });
        }
    }, [dispatch, pendingResponses]);

    useEffect(() => {
        scrollToBottom();
    }, [selectedChat?.messages, selectedChatId]);

    const scrollToBottom = () => {
        if (messageContainerRef.current) {
            messageContainerRef.current.scrollTop = messageContainerRef.current.scrollHeight;
        }
    };

    const getUsernameFromEmail = (email: string | undefined) => {
        return email ? email.split('@')[0] : 'user';
    };

    const getCursorPosition = (input: HTMLInputElement): { left: number } | null => {
        const computedStyle = window.getComputedStyle(input);
        const div = document.createElement('div');
        div.style.position = 'absolute';
        div.style.visibility = 'hidden';
        div.style.whiteSpace = 'pre';
        div.style.font = computedStyle.font;
        div.style.letterSpacing = computedStyle.letterSpacing;
        div.style.fontFamily = computedStyle.fontFamily;
        div.style.fontSize = computedStyle.fontSize;
        div.style.fontWeight = computedStyle.fontWeight;
        
        document.body.appendChild(div);
        
        const cursorPosition = input.selectionStart || 0;
        const textBeforeCursor = input.value.substring(0, cursorPosition);
        
        div.textContent = textBeforeCursor;
        const textWidth = div.clientWidth;
        
        document.body.removeChild(div);
        
        return { left: textWidth };
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>, data: { value: string }) => {
        const newValue = data.value;
        setMessage(newValue);
        
        if (!hasMention) {
            const atIndex = newValue.lastIndexOf('@');
            if (atIndex !== -1) {
                const lastSpaceIndex = newValue.lastIndexOf(' ', atIndex);
                const isAtStartOrAfterSpace = atIndex === 0 || lastSpaceIndex === atIndex - 1;
                
                if (isAtStartOrAfterSpace) {
                    const query = newValue.substring(atIndex + 1);
                    setMentionQuery(query);
                    
                    if (inputRef.current) {
                        const inputRect = inputRef.current.getBoundingClientRect();
                        const caretPosition = getCursorPosition(inputRef.current);
                        
                        setAutocompletePosition({
                            top: inputRect.top,
                            left: caretPosition ? inputRect.left + caretPosition.left : inputRect.left + 10
                        });
                        
                        setShowAutocomplete(true);
                    }
                }
            } else {
                setShowAutocomplete(false);
            }
        } else {
            if (!newValue.includes('@')) {
                setHasMention(false);
            }
        }
    };
    
    const handleMentionSelect = (agent: string) => {
        if (hasMention) return;
        
        const atIndex = message.lastIndexOf('@');
        if (atIndex !== -1) {
            const newMessage = message.substring(0, atIndex) + `@${agent} `;
            setMessage(newMessage);
            setHasMention(true);
            setShowAutocomplete(false);
            
            if (inputRef.current) {
                inputRef.current.focus();
                inputRef.current.selectionStart = newMessage.length;
                inputRef.current.selectionEnd = newMessage.length;
            }
        }
    };
    
    const handleAutocompleteClose = () => {
        setShowAutocomplete(false);
    };

    const handleQuickPrompt = (promptText: string) => {
        setMessage(promptText);
        if (inputRef.current) {
            inputRef.current.focus();
        }
    };

    const handleSend = async () => {
        if (!selectedChatId || (!message.trim()) || !user) return;

        const mentions = parseMentions(message, availableAgents);
        const targetAgent = getTargetAgent(mentions);

        const userMessage = {
            id: uuidv4(),
            content: message,
            sender: getUsernameFromEmail(user.email),
            timestamp: new Date(),
            isBot: false,
            mentions: mentions.length > 0 ? [...mentions] : undefined
        };

        dispatch(addMessage({ 
            chatId: selectedChatId, 
            message: userMessage
        }));

        setMessage('');
        dispatch(setLoading(true));
        dispatch(addPendingResponse({
            targetAgent,
            timestamp: new Date()
        }));

        try {
            await api.sendMessage(
                selectedChatId, 
                {
                    content: message,
                    sender: getUsernameFromEmail(user.email),
                    mentions: mentions.length > 0 ? [...mentions] : undefined
                },
                (botMessage) => {
                    dispatch(addMessage({
                        chatId: selectedChatId,
                        message: botMessage
                    }));
                    
                    if (pendingResponses && pendingResponses.length > 0) {
                        dispatch(removePendingResponse(targetAgent));
                    }
                }
            );
            
            dispatch(setLoading(false));
            
        } catch (error) {
            console.error('Error sending message:', error);
            dispatch(removePendingResponse(targetAgent));
            dispatch(setLoading(false));
            dispatch(addMessage({
                chatId: selectedChatId,
                message: {
                    id: uuidv4(),
                    content: "Sorry, there was an error processing your message. Please try again.",
                    sender: "System",
                    timestamp: new Date(),
                    isBot: true,
                }
            }));
        }
        
        setHasMention(false);
    };

    const isChatEmpty = !selectedChat || selectedChat.messages.length === 0;

    return (
        <div className={classes.container}>
            <div className={classes.messageContainer} ref={messageContainerRef}>
                {isChatEmpty ? (
                    <div className={classes.welcomeContainer}>
                        <BrandMark variant="icon" size={56} />
                        <h1 className={`${classes.welcomeTitle} animated-gradient`}>
                            Healthcare Agent Team
                        </h1>
                        <p className={classes.welcomeSubtitle}>
                            Collaborate with specialized clinical AI agents (Oncologist, Radiologist, Pathologist, Geneticist) for multi-disciplinary decision support.
                        </p>

                        <div className={classes.quickPromptsGrid}>
                            <div 
                                className={`glass-pill ${classes.quickPromptChip}`}
                                onClick={() => handleQuickPrompt('@oncologist Please review patient history for Case #4')}
                            >
                                <Sparkle24Regular style={{ color: '#0050FF' }} />
                                <span>@oncologist Review history for Case #4</span>
                            </div>
                            <div 
                                className={`glass-pill ${classes.quickPromptChip}`}
                                onClick={() => handleQuickPrompt('@radiologist Analyze imaging scan findings')}
                            >
                                <Sparkle24Regular style={{ color: '#0050FF' }} />
                                <span>@radiologist Analyze imaging scans</span>
                            </div>
                            <div 
                                className={`glass-pill ${classes.quickPromptChip}`}
                                onClick={() => handleQuickPrompt('@pathologist Summarize biopsy pathology report')}
                            >
                                <Sparkle24Regular style={{ color: '#0050FF' }} />
                                <span>@pathologist Summarize pathology</span>
                            </div>
                        </div>
                    </div>
                ) : (
                    <MessageList messages={selectedChat.messages} />
                )}
            </div>

            <div className={classes.inputContainer}>
                <div className={`glass-nav ${classes.inputRowWrapper}`}>
                    <Input
                        className={classes.input}
                        value={message} 
                        onChange={handleInputChange}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !showAutocomplete) {
                                handleSend();
                            }
                        }}
                        ref={inputRef}
                        placeholder="Type a message or use @ to mention an agent..."
                    />
                    <Button
                        className={classes.sendButton}
                        icon={<Send24Regular />}
                        onClick={handleSend}
                    >
                        <span className={classes.sendButtonText}>Send</span>
                    </Button>
                </div>
                
                <MentionAutocomplete
                    agents={availableAgents}
                    textAreaRef={inputRef}
                    isOpen={showAutocomplete}
                    onSelect={handleMentionSelect}
                    onClose={handleAutocompleteClose}
                    position={autocompletePosition}
                    query={mentionQuery}
                />
            </div>
        </div>
    );
}
