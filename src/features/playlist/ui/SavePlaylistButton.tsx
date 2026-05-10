import { BookmarkAddRounded } from '@mui/icons-material';
import { AppButton } from '../../../shared/ui/AppButton/AppButton';

type SavePlaylistButtonProps = {
  disabled?: boolean;
  onSave: () => void;
};

export const SavePlaylistButton = ({ disabled, onSave }: SavePlaylistButtonProps) => {
  return (
    <AppButton startIcon={<BookmarkAddRounded />} disabled={disabled} onClick={onSave}>
      Сохранить плейлист
    </AppButton>
  );
};
