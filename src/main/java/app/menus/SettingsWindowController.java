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
import app.menus.settingtabs.GeneralSettingController;
import app.menus.settingtabs.Viewer3DController;
import core.main.MainClass;

import com.programconst.ProgrammingConstsQE.SettingsTags;

public class SettingsWindowController implements Initializable {

    @FXML
    private TreeView<SettingsTags> treeNavigate;

    @FXML
    private Button saveButton,
    cancelButton,
    saveCloseButton;
    
    @FXML
    private BorderPane borderPaneMain;
    
    private MainClass mainClass;
    
    private GeneralSettingController contPath;
    
    private AnchorPane panePath;
    
    private Viewer3DController cont3d;
    
    private AnchorPane pane3d;
    
    public SettingsWindowController(MainClass mc) {
    	mainClass = mc;
    	
	}
    
	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		TreeItem<SettingsTags> treeRoot = new TreeItem<SettingsTags>(SettingsTags.Settings);
		treeNavigate.setRoot(treeRoot);treeNavigate.setShowRoot(false);//treeRoot.setExpanded(true);
		//tree items
		treeRoot.getChildren().add(new TreeItem<SettingsTags>(SettingsTags.General));
		TreeItem<SettingsTags> tiDefault = new TreeItem<SettingsTags>(SettingsTags.Viewer3D);
		treeRoot.getChildren().add(tiDefault);
		
		
		try {
			contPath = new GeneralSettingController(mainClass);
			FXMLLoader fxmlLoader1 = new FXMLLoader(getClass().getClassLoader().getResource("app/menus/settingtabs/generalSetting.fxml"));
			fxmlLoader1.setController(contPath);
			panePath = fxmlLoader1.load();
			
			cont3d = new Viewer3DController(mainClass);
			fxmlLoader1 = new FXMLLoader(getClass().getClassLoader().getResource("app/menus/settingtabs/viewer3d.fxml"));
			fxmlLoader1.setController(cont3d);
			pane3d = fxmlLoader1.load();
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		treeNavigate.getSelectionModel().selectedItemProperty().addListener((observable, oldValue, newValue) -> {
			if (newValue==null || newValue.getValue()==null) return;
			if (mainClass==null) return;
			
			
			switch(newValue.getValue()) {
				case General:
					borderPaneMain.setCenter(panePath);
					BorderPane.setAlignment(panePath, Pos.TOP_LEFT);
					//panePath.setStyle("-fx-background-color: blue");
					break;
				case Viewer3D:
					borderPaneMain.setCenter(pane3d);
					BorderPane.setAlignment(pane3d, Pos.TOP_LEFT);
					break;
				default:
			}
		});
		treeNavigate.getSelectionModel().select(tiDefault);
		
		saveButton.setOnAction((event) -> {
			saveChanges();
		});
	    cancelButton.setOnAction((event) -> {
	    	closeStage();
		});
	    saveCloseButton.setOnAction((event) -> {
	    	saveChanges();
	    	closeStage();
		});
	}
	private void saveChanges() {
		contPath.saveChanges();
		cont3d.saveChanges();
	}
	private void closeStage() {
        Stage stage  = (Stage) borderPaneMain.getScene().getWindow();
        stage.close();
    }

}