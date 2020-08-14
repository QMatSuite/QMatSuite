/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.input.geo;

import java.net.URL;
import java.util.List;
import java.util.ResourceBundle;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import javafx.beans.binding.Bindings;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.fxml.FXML;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.ComboBox;
import javafx.scene.control.Label;
import javafx.scene.control.TableCell;
import javafx.scene.control.TableColumn;
import javafx.scene.control.TableView;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleButton;
import javafx.scene.control.Alert.AlertType;
import javafx.scene.control.cell.PropertyValueFactory;
import javafx.scene.paint.Color;
import agent.InputAgentGeo;
import core.app.input.InputController;
import core.main.MainClass;

import com.consts.ChemicalElements;
import com.consts.Constants.EnumStep;
import com.consts.Constants.EnumUnitAtomPos;

public class InputGeoAtomsController extends InputController{

	@FXML private ComboBox<String> unitCombo;//ok

    @FXML private Button infoButton,
    deleteAtom,
    editAtom,
    clearInput;//ok except infoButton
    
    @FXML
    private Button buttonAddEnd,
    buttonAddBegin,
    buttonAddAfter,
    buttonAddBefore;

    @FXML private TableView<Atom> atomTable;//ok

    @FXML private TableColumn<Atom, Integer> indexColumn;//ok
    
    @FXML private TableColumn<Atom, Coordinate> xColumn,
    yColumn,
    zColumn;//ok
    
    @FXML private TableColumn<Atom, String> elementColumn;//ok
    
    @FXML private Label labelBottom;//ok
    
    @FXML private Label alat;
    
    @FXML private TextField textElem,
    textX,
    textY,
    textZ;
    
    @FXML private ToggleButton fixX,
    fixY,
    fixZ;
    
    private ObservableList<Atom> atomsData;
    
    private final List<String> enumElementsNames= Stream.of(ChemicalElements.values()).map(Enum::name)
	        .collect(Collectors.toList());
    
	private final List<String> enumUnitNames = Stream.of(EnumUnitAtomPos.values())
            .map(Enum::name)
            .collect(Collectors.toList());
	
	
	public InputGeoAtomsController(MainClass mc) {
		super(mc, EnumStep.GEO);
		atomsData = FXCollections.observableArrayList();
	}
    public Label getAlat() {
    	return alat;
    }
    @Override
    public void initialize(URL location, ResourceBundle resources) {
    	alat.setMaxWidth(60);
    	fixX.setSelected(false);fixY.setSelected(false);fixZ.setSelected(false);
    	setupTable();
    	
    	buttonAddBegin.setOnAction((event) -> {	
    		Atom tmp = genAtomFromInput();
    		if (tmp==null) return;
			atomsData.add(0,tmp);
			InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (iGeo!=null) {
				iGeo.atomList.add(0,tmp);
				iGeo.updateElemListAll();//*********very inefficient
				mainClass.projectManager.updateViewerPlot();
			}
			atomTable.getSelectionModel().select(0);
		});
    	buttonAddEnd.setOnAction((event) -> {	
    		Atom tmp = genAtomFromInput();
    		if (tmp==null) return;
			atomsData.add(tmp);
			InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (iGeo!=null) {
				iGeo.atomList.add(tmp);
				iGeo.updateElemListAll();//*********very inefficient
				mainClass.projectManager.updateViewerPlot();
			}
			atomTable.getSelectionModel().selectLast();
		});
    	buttonAddBefore.setOnAction((event) -> {
    		int selec = atomTable.getSelectionModel().getSelectedIndex();
    		if (selec<0 || selec >= atomsData.size()) {labelBottom.setText("Nothing selected. Cannot add relative to the selection.");return;}
    		labelBottom.setText("");
    		
    		Atom tmp = genAtomFromInput();
    		if (tmp==null) return;
    		
			atomsData.add(selec,tmp);
			InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (iGeo!=null) {
				iGeo.atomList.add(selec,tmp);
				iGeo.updateElemListAll();//*********very inefficient
				mainClass.projectManager.updateViewerPlot();
			}
			atomTable.getSelectionModel().select(selec);
		});
    	buttonAddAfter.setOnAction((event) -> {	
    		int selec = atomTable.getSelectionModel().getSelectedIndex();
    		if (selec<0 || selec >= atomsData.size()) {labelBottom.setText("Nothing selected. Cannot add relative to the selection.");return;}
    		labelBottom.setText("");
    		
    		Atom tmp = genAtomFromInput();
    		if (tmp==null) return;
    		
			atomsData.add(selec+1,tmp);
			InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (iGeo!=null) {
				iGeo.atomList.add(selec+1,tmp);
				iGeo.updateElemListAll();//*********very inefficient
				mainClass.projectManager.updateViewerPlot();
			}
			atomTable.getSelectionModel().select(selec+1);
		});
    	editAtom.setOnAction((event) -> {	
    		int selec = atomTable.getSelectionModel().getSelectedIndex();
    		if (selec<0 || selec >= atomsData.size()) {labelBottom.setText("Index out of bound to be editted.");return;}
    		labelBottom.setText("");
    		
    		Atom tmp = genAtomFromInput();//******is this efficient or shall we change properties of Atom?
    		if (tmp==null) return;
    		atomsData.set(selec, tmp);
			InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (iGeo==null) {labelBottom.setText("Null input geo agent.");return;}
			iGeo.atomList.set(selec, tmp);
			iGeo.updateElemListAll();//*********very inefficient
			mainClass.projectManager.updateViewerPlot();
    		
			atomTable.getSelectionModel().select(selec);
		});
    	deleteAtom.setOnAction((event) -> {	
    		int selec = atomTable.getSelectionModel().getSelectedIndex();
    		if (selec<0 || selec >= atomsData.size()) {labelBottom.setText("No data is selected to be deleted.");return;}
    		labelBottom.setText("");
    		atomsData.remove(selec);
			InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
			if (iGeo!=null) {
				iGeo.atomList.remove(selec);
				iGeo.updateElemListAll();//*********very inefficient
				mainClass.projectManager.updateViewerPlot();
			}
			atomTable.getSelectionModel().selectNext();
		});
    	clearInput.setOnAction((event) -> {	
    		clearInput();
		});
    	
    	
    	unitCombo.getItems().addAll(enumUnitNames);
    	unitCombo.setOnAction((event) -> {	
			if (unitCombo.getValue()!=null && enumUnitNames.contains(unitCombo.getValue())) {
				InputAgentGeo iGeo = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
				if (iGeo!=null) {
					try {
						iGeo.needAlatFromAtom=false;
						switch (EnumUnitAtomPos.valueOf(unitCombo.getValue())) {
							case alat:
								iGeo.unitAtomPos=EnumUnitAtomPos.alat;alat.setVisible(true);iGeo.needAlatFromAtom=true;
								break;
							case bohr:
								iGeo.unitAtomPos=EnumUnitAtomPos.bohr;alat.setVisible(false);
								break;
							case angstrom:
								iGeo.unitAtomPos=EnumUnitAtomPos.angstrom;alat.setVisible(false);
								break;
							case crystal:
								iGeo.unitAtomPos=EnumUnitAtomPos.crystal;alat.setVisible(false);
								break;
							default:
								Alert alert = new Alert(AlertType.INFORMATION);
						    	alert.setTitle("Error");
						    	alert.setContentText(unitCombo.getValue()+" is invalid for unit!");
						    	alert.showAndWait();	
						    	break;
						}
						mainClass.projectManager.updateViewerPlot();
					}catch (Exception e) {
						Alert alert = new Alert(AlertType.INFORMATION);
				    	alert.setTitle("Exception!");
				    	alert.setContentText(e.getMessage());
				    	alert.showAndWait();
					}
					
				}
			}
    	});
    }
    
    private void setupTable() {
    	//ObservableList<Atom> atomsData =FXCollections.observableArrayList(new Atom("C",1),new Atom("H",2),new Atom("He",3));
		indexColumn.setCellValueFactory(new PropertyValueFactory<Atom, Integer>("index"));
		indexColumn.setCellFactory(col -> {
		    TableCell<Atom, Integer> cell = new TableCell<>();
		    cell.textProperty().bind(Bindings.createStringBinding(() -> {
		        if (cell.isEmpty()) {
		            return null ;
		        } else {
		            return Integer.toString(cell.getIndex()+1);
		        }
		    }, cell.emptyProperty(), cell.indexProperty()));
		    return cell ;
		});
		elementColumn.setCellValueFactory(new PropertyValueFactory<Atom, String>("atomSpecies"));
		xColumn.setCellValueFactory(new PropertyValueFactory<Atom, Coordinate>("xcoor"));
		yColumn.setCellValueFactory(new PropertyValueFactory<Atom, Coordinate>("ycoor"));
		zColumn.setCellValueFactory(new PropertyValueFactory<Atom, Coordinate>("zcoor"));
		
		atomTable.setItems(atomsData);
		
		//not editable at the moment
		
//		atomTable.setEditable(true);
//		elementColumn.setCellFactory(TextFieldTableCell.forTableColumn());
//		elementColumn.setOnEditCommit(new EventHandler<CellEditEvent<Atom, String>>() {
//	        @Override
//	        public void handle(CellEditEvent<Atom, String> t) {
//	            ((Atom) t.getTableView().getItems().get(
//	                t.getTablePosition().getRow())
//	                ).setAtomSpecies(t.getNewValue());;
//	        }
//	    });

		// Custom rendering of the table cell.
		xColumn.setCellFactory(column -> {
		    return new TableCell<Atom, Coordinate>() {
		        @Override
		        protected void updateItem(Coordinate item, boolean empty) {
		            super.updateItem(item, empty);

		            if (item == null || empty) {
		                setText(null);
		                setStyle("");
		            } else {

		                setText(item.toString());

		                if (item.getBoolFix()) {
		                    setTextFill(Color.CHOCOLATE);
		                    setStyle("-fx-background-color: yellow");
		                } else {
		                    setTextFill(Color.BLACK);
		                    setStyle("");
		                }
		            }
		        }
		    };
		});
		yColumn.setCellFactory(column -> {
		    return new TableCell<Atom, Coordinate>() {
		        @Override
		        protected void updateItem(Coordinate item, boolean empty) {
		            super.updateItem(item, empty);

		            if (item == null || empty) {
		                setText(null);
		                setStyle("");
		            } else {

		                setText(item.toString());

		                if (item.getBoolFix()) {
		                    setTextFill(Color.CHOCOLATE);
		                    setStyle("-fx-background-color: yellow");
		                } else {
		                    setTextFill(Color.BLACK);
		                    setStyle("");
		                }
		            }
		        }
		    };
		});
		zColumn.setCellFactory(column -> {
		    return new TableCell<Atom, Coordinate>() {
		        @Override
		        protected void updateItem(Coordinate item, boolean empty) {
		            super.updateItem(item, empty);

		            if (item == null || empty) {
		                setText(null);
		                setStyle("");
		            } else {

		                setText(item.toString());

		                if (item.getBoolFix()) {
		                    setTextFill(Color.CHOCOLATE);
		                    setStyle("-fx-background-color: yellow");
		                } else {
		                    setTextFill(Color.BLACK);
		                    setStyle("");
		                }
		            }
		        }
		    };
		});
		atomTable.getSelectionModel().selectedItemProperty().addListener((obs, oldSelect, newSelect) -> {
		    if (newSelect == null) {
		    	clearInput();
		    }
		    else {
		    	textElem.setText(newSelect.getAtomSpecies().toString());
		    	textX.setText(newSelect.getXcoor().getX().toString());
		    	textY.setText(newSelect.getYcoor().getX().toString());
		    	textZ.setText(newSelect.getZcoor().getX().toString());
		    	fixX.setSelected(newSelect.getXcoor().getBoolFix());
		    	fixY.setSelected(newSelect.getYcoor().getBoolFix());
		    	fixZ.setSelected(newSelect.getZcoor().getBoolFix());
		    }
		});
    }
    private Atom genAtomFromInput() {
    	if (!enumElementsNames.contains(textElem.getText().trim())) {
			labelBottom.setText("Error! Invalid element. Please use the format of H,He,Li,Be,...");return null;
		}
		Double x_coor,
		y_coor,
		z_coor;
		
		try {
			x_coor=Double.valueOf(textX.getText());
			y_coor=Double.valueOf(textY.getText());
			z_coor=Double.valueOf(textZ.getText());
		}
		catch (Exception e) {
			labelBottom.setText("Not number in X/Y/Z. ");return null;
		}
		Atom tmp = new Atom(textElem.getText().trim(),x_coor,y_coor,z_coor,fixX.isSelected(),fixY.isSelected(),fixZ.isSelected());
		labelBottom.setText("");
		return tmp;
    }
    private void clearInput() {
    	labelBottom.setText("");
		textElem.setText("");textX.setText("");textY.setText("");textZ.setText("");
		fixX.setSelected(false);fixY.setSelected(false);fixZ.setSelected(false);
		atomTable.getSelectionModel().clearSelection();
    }
    public void loadProjectParameters() {
    	InputAgentGeo ia = (InputAgentGeo) mainClass.projectManager.getCurrentGeoAgent();
    	if (ia==null) return;
    	clearInput();
    	if (!unitCombo.getItems().isEmpty()) {
			if (ia.unitAtomPos==null) {unitCombo.getSelectionModel().clearSelection();return;}
        	switch (ia.unitAtomPos){
	        	case alat:unitCombo.setValue(EnumUnitAtomPos.alat.toString());alat.setVisible(true);break;
	        	case bohr:unitCombo.setValue(EnumUnitAtomPos.bohr.toString());alat.setVisible(false);break;
	        	case angstrom:unitCombo.setValue(EnumUnitAtomPos.angstrom.toString());alat.setVisible(false);break;
	        	case crystal:unitCombo.setValue(EnumUnitAtomPos.crystal.toString());alat.setVisible(false);break;
        		default:
        			Alert alert = new Alert(AlertType.INFORMATION);
			    	alert.setTitle("Error");
			    	alert.setContentText(ia.ibrav+" is invalid for ibrav!");
			    	alert.showAndWait();	
			    	break;
        	}
    	}
    	atomsData.clear();
    	atomsData.addAll(ia.atomList);
    	mainClass.projectManager.updateViewerPlot();//*****not so efficient
	}

}
