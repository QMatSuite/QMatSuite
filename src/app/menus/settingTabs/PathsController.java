package app.menus.settingTabs;

import java.io.File;
import java.net.URL;
import java.nio.file.Paths;
import java.util.ResourceBundle;

import com.consts.DefaultFileNames.settingKeys;
import com.programConst.Coloring;

import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.geometry.Insets;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.TextField;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.Background;
import javafx.scene.layout.BackgroundFill;
import javafx.scene.layout.CornerRadii;
import javafx.stage.DirectoryChooser;
import javafx.stage.Stage;
import main.MainClass;

public class PathsController implements Initializable{

	@FXML private AnchorPane acp;
	
    @FXML
    private Button openWorkspaceButton;

    @FXML
    private Button openQEPathButton;

    @FXML
    private TextField textWorkspace;

    @FXML
    private TextField textQEPath;

    private MainClass mainClass;
    
    public PathsController(MainClass mc) {
    	mainClass = mc;
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		textQEPath.setBackground(new Background(new BackgroundFill(Coloring.defaultFile, 
				CornerRadii.EMPTY, Insets.EMPTY)));
		
		openQEPathButton.setOnAction((event) -> {

			DirectoryChooser dirChooser = new DirectoryChooser ();
			
			//go to current directory
			String currentPath = Paths.get(".").toAbsolutePath().normalize().toString();
			File tmpFile = new File(currentPath);
			if(tmpFile!=null && tmpFile.canRead()) {
				dirChooser.setInitialDirectory(tmpFile);
			}
			
			File selectedDir = dirChooser.showDialog((Stage)acp.getScene().getWindow());
			
			if(selectedDir!=null && selectedDir.canRead()) {
				mainClass.projectManager.qePath = selectedDir.getPath();
				textQEPath.setText(selectedDir.getPath());
				mainClass.projectManager.writeGlobalSettings(settingKeys.qePath.toString(),selectedDir.getPath());
				textQEPath.setBackground(new Background(new BackgroundFill(Coloring.validFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
			
		});
	}
	public void loadPaths() {
		String workSpacePath = mainClass.projectManager.workSpacePath;
		String qePath = mainClass.projectManager.qePath;
		if (workSpacePath!=null) {
			textWorkspace.setText(workSpacePath);
			File wsDir = new File(workSpacePath);
			if(wsDir!=null && wsDir.canRead()) {
				textWorkspace.setBackground(new Background(new BackgroundFill(Coloring.validFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
			else {
				textWorkspace.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
		}
		else {
			textWorkspace.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
					CornerRadii.EMPTY, Insets.EMPTY)));
		}
		
		if(qePath!=null) {
			textQEPath.setText(qePath);
			File qeDir = new File(qePath);
			if(qeDir!=null && qeDir.canRead()) {
				textQEPath.setBackground(new Background(new BackgroundFill(Coloring.validFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
			else {
				textQEPath.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
						CornerRadii.EMPTY, Insets.EMPTY)));
			}
		}
		else {
			textQEPath.setBackground(new Background(new BackgroundFill(Coloring.invalidFile, 
					CornerRadii.EMPTY, Insets.EMPTY)));
		}
	}
}