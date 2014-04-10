-- Включение разрешения изменения расширенных опций.
EXEC sp_configure 'show advanced options', 1
GO
-- Обновление текущих настроек расширенных опций.
RECONFIGURE
GO
-- Включение возможности запуска внешних программ.
EXEC sp_configure 'xp_cmdshell', 1
GO
-- Обновление текущих настроек для запуска внешних программ.
RECONFIGURE
GO


SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO

DROP TRIGGER dbo.OnUpdate 
GO
-- =============================================
-- Author:		<julia.goncharova@lamoda.ru>
-- Create date: <10.04.14>
-- Description:	<sinc 1c with git>
-- =============================================
CREATE TRIGGER dbo.OnUpdate 
   ON  [1s-msk-4Git-dev].dbo.Config 
   AFTER UPDATE
AS 
BEGIN
	DECLARE @skript_path varchar(100)
	DECLARE @command varchar(150)
	SET @skript_path = 'C:\1CUnit\1C2Git\'
	SET @command='python '+@skript_path+'1C2Git.py -s >'+@skript_path+'sql_update.txt'
	EXEC master..xp_cmdshell @command 
END
GO
