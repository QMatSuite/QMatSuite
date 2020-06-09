/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.menus;

import java.io.IOException;
import java.net.URL;
import java.util.ResourceBundle;

import com.programconst.ProgrammingConsts.SettingsTags;

import app.menus.settingtabs.PathsController;
import javafx.fxml.FXML;
import javafx.fxml.FXMLLoader;
import javafx.fxml.Initializable;
import javafx.geometry.Pos;
import javafx.scene.control.Button;
import javafx.scene.control.TreeItem;
import javafx.scene.control.TreeView;
import javafx.scene.layout.AnchorPane;
import javafx.scene.layout.BorderPane;
import javafx.stage.Stage;
import main.MainClass;

public class SettingsWindowController implements Initializable {

    @FXML
    private TreeView<SettingsTags> treeNavigate;

    @FXML
    private Button saveButton;

    @FXML
    private Button saveCloseButton;

    @FXML
    private Button cancelButton;

    @FXML
    private BorderPane borderPaneMain;
    
    private MainClass mainClass;
    
    private PathsController contPath;
    
    private AnchorPane panePath;
    
    public SettingsWindowController(MainClass mc) {
    	mainClass = mc;
    	
	}
    
	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		TreeItem<SettingsTags> treeRoot = new TreeItem<SettingsTags>(SettingsTags.Settings);
		treeNavigate.setRoot(treeRoot);treeNavigate.setShowRoot(false);//treeRoot.setExpanded(true);
		//tree items
		treeRoot.getChildren().add(new TreeItem<SettingsTags>(SettingsTags.Paths));
		treeRoot.getChildren().add(new TreeItem<SettingsTags>(SettingsTags.Viewer3D));
		
		try {
			contPath = new PathsController(mainClass);
			FXMLLoader fxmlLoader1 = new FXMLLoader(this.getClass().getResource("settingTabs/paths.fxml"));
			fxmlLoader1.setController(contPath);
			panePath = fxmlLoader1.load();
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		treeNavigate.getSelectionModel().selectedItemProperty().addListener((observable, oldValue, newValue) -> {
			if (newValue==null || newValue.getValue()==null) return;
			if (mainClass==null) return;
			
			
			switch(newValue.getValue()) {
				case Paths:
					borderPaneMain.setCenter(panePath);
					BorderPane.setAlignment(panePath, Pos.TOP_LEFT);
					//panePath.setStyle("-fx-background-color: blue");
					contPath.loadPaths();
					break;
				case Viewer3D:
					break;
				default:
			}
		});

	    saveButton.setOnAction((event) -> {
	    	saveChanges();
		});
	    saveCloseButton.setOnAction((event) -> {
	    	saveChanges();
	    	closeStage();
		});
	    cancelButton.setOnAction((event) -> {
	    	cancelChanges();
		});
	}
	private void cancelChanges() {
		//to be done later
	}
	private void saveChanges() {
		//to be done later
	}
	private void closeStage() {
        Stage stage  = (Stage) borderPaneMain.getScene().getWindow();
        stage.close();
    }

}