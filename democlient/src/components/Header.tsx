import {
    Button,
    makeStyles,
    Menu,
    MenuTrigger,
    MenuPopover,
    MenuList,
    MenuItem,
    Avatar
} from '@fluentui/react-components';
import { Person24Regular, SignOut24Regular, Navigation24Regular } from '@fluentui/react-icons';
import { useAuth } from '../contexts/AuthContext';
import BrandMark from './BrandMark';

interface HeaderProps {
    toggleSidebar?: () => void;
    isMobile?: boolean;
}

const useStyles = makeStyles({
    header: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.75rem 1.5rem',
        zIndex: 20,
    },
    leftSection: {
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
    },
    profileButton: {
        borderRadius: '9999px',
        padding: '6px 14px',
    },
    menuButton: {
        borderRadius: '9999px',
    }
});

export default function Header({ toggleSidebar, isMobile }: HeaderProps) {
    const classes = useStyles();
    const { user, logout } = useAuth();

    const handleLogout = () => {
        logout();
    };

    return (
        <header className={`glass-nav ${classes.header}`}>
            <div className={classes.leftSection}>
                {isMobile && toggleSidebar && (
                    <Button 
                        appearance="subtle"
                        icon={<Navigation24Regular />}
                        onClick={toggleSidebar}
                        className={classes.menuButton}
                        aria-label="Toggle chat list"
                    />
                )}
                <BrandMark variant="full" />
            </div>
            {user && (
                <Menu>
                    <MenuTrigger>
                        <Button
                            appearance="transparent"
                            className={`glass-pill ${classes.profileButton}`}
                            icon={<Avatar icon={<Person24Regular />} size={24} style={{ backgroundColor: '#0050FF', color: '#ffffff' }} />}
                        >
                            <span style={{ fontWeight: 600, color: '#0f172a' }}>
                                {user.name || user.email || 'User'}
                            </span>
                        </Button>
                    </MenuTrigger>
                    <MenuPopover style={{ borderRadius: '16px', padding: '6px' }}>
                        <MenuList>
                            <MenuItem icon={<SignOut24Regular />} onClick={handleLogout} style={{ borderRadius: '8px' }}>
                                Sign Out
                            </MenuItem>
                        </MenuList>
                    </MenuPopover>
                </Menu>
            )}
        </header>
    );
}
