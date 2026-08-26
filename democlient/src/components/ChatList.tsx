import { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
    Button,
    makeStyles,
    List,
    ListItem,
    Dialog,
    DialogTrigger,
    DialogSurface,
    DialogTitle,
    DialogBody,
    DialogActions,
    DialogContent,
    Input
} from '@fluentui/react-components';
import { 
    Add24Regular, 
    Delete24Regular, 
    Edit24Regular,
    CheckmarkCircle24Regular,
    DismissCircle24Regular,
    Chat24Regular
} from '@fluentui/react-icons';
import { RootState } from '../store/store';
import { selectChat, addChat, deleteChat, updateChatTitle } from '../store/slices/chatSlice';
import { v4 as uuidv4 } from 'uuid';
import type { Chat } from '../types';

interface ChatListProps {
    onSelectChat?: () => void;
}

const useStyles = makeStyles({
    container: {
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
    },
    header: {
        padding: '1.25rem 1rem 1rem 1rem',
    },
    newChatButton: {
        width: '100%',
        borderRadius: '9999px',
        backgroundColor: '#0050FF',
        color: '#ffffff',
        fontWeight: '600',
        padding: '10px 18px',
        boxShadow: '0 4px 14px rgba(0, 80, 255, 0.25)',
        '&:hover': {
            backgroundColor: '#0044db',
            color: '#ffffff',
            transform: 'translateY(-1px)',
            boxShadow: '0 6px 18px rgba(0, 80, 255, 0.35)',
        },
    },
    list: {
        flex: 1,
        overflow: 'auto',
        padding: '0.75rem 0.75rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
    },
    listItem: {
        cursor: 'pointer',
        padding: '0.75rem 1rem',
        margin: '2px 0',
        borderRadius: '9999px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: 'transparent',
        '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            transform: 'translateX(2px)',
        },
        '&:hover .hoverActionButton': {
            opacity: 1,
        },
    },
    selectedItem: {
        backgroundColor: '#ffffff',
        boxShadow: '0 4px 12px rgba(0, 80, 255, 0.08)',
        fontWeight: '600',
        '&:hover': {
            backgroundColor: '#ffffff',
        },
    },
    chatTitle: {
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        color: '#0f172a',
        fontSize: '0.9rem',
    },
    chatIcon: {
        color: '#0050FF',
    },
    hoverActionButton: {
        opacity: 0,
        minWidth: '28px',
        height: '28px',
        padding: '2px',
        borderRadius: '9999px',
    },
    editActionButton: {
        minWidth: '28px',
        height: '28px',
        padding: '2px',
        borderRadius: '9999px',
    },
    actionButtons: {
        display: 'flex',
        gap: '4px',
    },
    editInput: {
        flex: 1,
        marginRight: '8px',
    },
    dialogContent: {
        padding: '20px',
        maxWidth: '450px',
    },
    dialogActions: {
        paddingBottom: '20px',
        paddingRight: '20px',
    }
});

interface EditingState {
    chatId: string;
    title: string;
}

export default function ChatList({ onSelectChat }: ChatListProps) {
    const classes = useStyles();
    const dispatch = useDispatch();
    const chats = useSelector((state: RootState) => state.chat.chats);
    const selectedChatId = useSelector((state: RootState) => state.chat.selectedChatId);
    const [editing, setEditing] = useState<EditingState | null>(null);

    const handleNewChat = () => {
        const newId = uuidv4();
        const newChat: Chat = {
            id: newId,
            title: 'New Discussion',
            messages: [],
            createdAt: new Date()
        };
        
        dispatch(addChat(newChat));
        dispatch(selectChat(newId));
        
        if (onSelectChat) {
            onSelectChat();
        }
    };

    const handleSelectChat = (chatId: string) => {
        dispatch(selectChat(chatId));
        if (onSelectChat) {
            onSelectChat();
        }
    };

    const handleDeleteChat = (chatId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        dispatch(deleteChat(chatId));
    };

    const startEditing = (chat: Chat, e: React.MouseEvent) => {
        e.stopPropagation();
        setEditing({ chatId: chat.id, title: chat.title });
    };

    const cancelEditing = (e: React.MouseEvent) => {
        e.stopPropagation();
        setEditing(null);
    };

    const saveEditing = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (editing) {
            dispatch(updateChatTitle({ chatId: editing.chatId, title: editing.title }));
            setEditing(null);
        }
    };

    return (
        <div className={`glass-sidebar ${classes.container}`}>
            <div className={classes.header}>
                <Button
                    icon={<Add24Regular />}
                    onClick={handleNewChat}
                    className={classes.newChatButton}
                >
                    + New Discussion
                </Button>
            </div>
            <List className={classes.list}>
                {chats.map(chat => (
                    <ListItem
                        key={chat.id}
                        className={`${classes.listItem} ${chat.id === selectedChatId ? classes.selectedItem : ''}`}
                        onClick={() => handleSelectChat(chat.id)}
                    >
                        {editing?.chatId === chat.id ? (
                            <>
                                <Input 
                                    className={classes.editInput}
                                    value={editing.title}
                                    onChange={(e, data) => setEditing({ ...editing, title: data.value })}
                                    onClick={(e) => e.stopPropagation()}
                                />
                                <div className={classes.actionButtons}>
                                    <Button
                                        className={classes.editActionButton}
                                        appearance="subtle"
                                        icon={<CheckmarkCircle24Regular style={{ color: '#0050FF' }} />}
                                        onClick={saveEditing}
                                    />
                                    <Button
                                        className={classes.editActionButton}
                                        appearance="subtle"
                                        icon={<DismissCircle24Regular />}
                                        onClick={cancelEditing}
                                    />
                                </div>
                            </>
                        ) : (
                            <>
                                <div className={classes.chatTitle}>
                                    <Chat24Regular className={chat.id === selectedChatId ? classes.chatIcon : undefined} style={{ opacity: chat.id === selectedChatId ? 1 : 0.4 }} />
                                    <span>{chat.title}</span>
                                </div>
                                <div className={classes.actionButtons}>
                                    <Button
                                        className={`hoverActionButton ${classes.hoverActionButton}`}
                                        appearance="subtle"
                                        icon={<Edit24Regular />}
                                        onClick={(e) => startEditing(chat, e)}
                                        title="Edit chat title"
                                    />
                                    <Dialog>
                                        <DialogTrigger disableButtonEnhancement>
                                            <Button
                                                className={`hoverActionButton ${classes.hoverActionButton}`}
                                                appearance="subtle"
                                                icon={<Delete24Regular />}
                                                onClick={(e) => e.stopPropagation()}
                                                title="Delete chat"
                                            />
                                        </DialogTrigger>
                                        <DialogSurface style={{ borderRadius: '20px' }}>
                                            <DialogBody>
                                                <DialogContent className={classes.dialogContent}>
                                                    <DialogTitle>Delete Discussion</DialogTitle>
                                                    <p>Are you sure you want to delete this chat session? This action cannot be undone.</p>
                                                </DialogContent>
                                                <DialogActions className={classes.dialogActions}>
                                                    <DialogTrigger disableButtonEnhancement>
                                                        <Button appearance="secondary" style={{ borderRadius: '9999px' }}>Cancel</Button>
                                                    </DialogTrigger>
                                                    <DialogTrigger disableButtonEnhancement>
                                                        <Button 
                                                            appearance="primary"
                                                            style={{ backgroundColor: '#dc2626', borderRadius: '9999px' }}
                                                            onClick={(e) => handleDeleteChat(chat.id, e)}
                                                        >
                                                            Delete
                                                        </Button>
                                                    </DialogTrigger>
                                                </DialogActions>
                                            </DialogBody>
                                        </DialogSurface>
                                    </Dialog>
                                </div>
                            </>
                        )}
                    </ListItem>
                ))}
            </List>
        </div>
    );
}
